"""Audio-based highlight (and "learning moment") detection.

FunClip's core workflow finds clips by matching text in the ASR transcript.
That doesn't work for footage with little or no dialogue to transcribe -
e.g. raw sports recordings, where the audio is mostly ambient/crowd noise
rather than speech (confirmed via ASR testing: both bundled models produce
garbage output on this kind of content, because there's genuinely little
speech there to recognize).

For that case, this looks for two different audio signatures instead:

- Highlights: sudden spikes in audio energy - the crowd/players reacting
  to something happening, which in practice tends to follow the actual
  highlight moment (a good rally, a point scored) by a couple of seconds.
- Learning moments: a sustained rally (a run of above-baseline "action"
  noise - the run of a play) that ends WITHOUT a reaction spike - fading
  back to quiet instead of a cheer. That pattern tends to correspond to a
  play ending anticlimactically (an error, a stoppage) rather than a
  celebrated point.

Both are heuristics, not real gameplay understanding, so results should be
treated as candidates to skim and confirm by watching, not a guaranteed-
accurate reel either way.
"""
import os

import numpy as np
import librosa
import moviepy.editor as mpy


def _format_srt_time(seconds):
    """Convert seconds to the HH:MM:SS,mmm format extract_timestamps() expects."""
    if seconds < 0:
        seconds = 0
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3600000)
    minutes, rem = divmod(rem, 60000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _compute_relative_energy(video_filename, window_seconds=0.5):
    """Load a video's audio and return (relative_energy, duration, window_seconds).

    relative_energy[i] is window i's loudness in dB relative to a ~20s
    rolling local baseline - positive means louder than this video's own
    recent noise floor, not an absolute loudness measure.
    """
    video = mpy.VideoFileClip(video_filename)
    if video.audio is None:
        return None, 0.0, window_seconds

    base_name, _ = os.path.splitext(video_filename)
    audio_file = base_name + '_highlight_tmp.wav'
    video.audio.write_audiofile(audio_file, logger=None)
    try:
        y, sr = librosa.load(audio_file, sr=16000, mono=True)
    finally:
        if os.path.exists(audio_file):
            os.remove(audio_file)

    duration = len(y) / sr
    hop = int(window_seconds * sr)
    n_windows = max(1, len(y) // hop)
    energy = np.array([
        np.sqrt(np.mean(np.square(y[i * hop:(i + 1) * hop])))
        if len(y[i * hop:(i + 1) * hop]) else 0.0
        for i in range(n_windows)
    ])
    # dB-like scale (with a floor so silence doesn't produce -inf).
    energy_db = 20 * np.log10(energy + 1e-6)

    baseline_windows = max(1, int(20.0 / window_seconds))  # ~20s of context
    baseline = np.array([
        np.median(energy_db[max(0, i - baseline_windows): i + 1])
        for i in range(len(energy_db))
    ])
    return energy_db - baseline, duration, window_seconds


def detect_audio_highlights(video_filename, top_n=6, lead_seconds=8.0, trail_seconds=2.0,
                             min_gap_seconds=15.0, window_seconds=0.5):
    """Find candidate highlight moments by audio-energy spikes in a video.

    Returns text in the same "N. [start-end] label" format the LLM Clipping
    result box produces, so it can be fed straight into the existing AI Clip
    / AI Clip+Subtitles buttons without any other UI changes.
    """
    relative, duration, window_seconds = _compute_relative_energy(video_filename, window_seconds)
    if relative is None:
        return "No audio track found in this video; can't detect audio-based highlights."
    if duration <= lead_seconds + trail_seconds:
        return "Video is too short for highlight detection."

    threshold = max(np.percentile(relative, 90), 3.0)  # top ~10%, min +3dB

    candidates = []
    for i in range(1, len(relative) - 1):
        if relative[i] >= threshold and relative[i] >= relative[i - 1] and relative[i] >= relative[i + 1]:
            candidates.append((i * window_seconds, relative[i]))

    if not candidates:
        return ("No clear audio spikes found - this video may not have distinct "
                "crowd/reaction moments to detect.")

    # Strongest spikes first, then non-max suppression so the same crowd
    # reaction isn't picked multiple times.
    candidates.sort(key=lambda c: c[1], reverse=True)
    selected = []
    for t, score in candidates:
        if all(abs(t - st) >= min_gap_seconds for st, _ in selected):
            selected.append((t, score))
        if len(selected) >= top_n:
            break

    if not selected:
        return ("No clear audio spikes found - this video may not have distinct "
                "crowd/reaction moments to detect.")

    selected.sort(key=lambda c: c[0])  # chronological order for a natural clip list

    lines = []
    for idx, (t, score) in enumerate(selected, start=1):
        start = max(0.0, t - lead_seconds)
        end = min(duration, t + trail_seconds)
        lines.append(
            f"{idx}. [{_format_srt_time(start)}-{_format_srt_time(end)}] "
            f"Possible highlight (audio spike at {_format_srt_time(t)}, "
            f"+{score:.1f}dB above local baseline)"
        )
    return "\n".join(lines)


def detect_learning_moments(video_filename, top_n=6, lead_seconds=10.0, trail_seconds=2.0,
                             min_gap_seconds=15.0, window_seconds=0.5,
                             min_rally_seconds=3.0, active_threshold_db=-2.0,
                             cheer_threshold_db=3.0, quiet_check_seconds=3.0):
    """Find candidate "learning moment" clips: a sustained rally that ends
    WITHOUT a crowd/player reaction spike, unlike a celebrated point.

    Same output format as detect_audio_highlights(), so it also feeds
    straight into the existing AI Clip buttons. This is a rougher heuristic
    than highlight detection (there's no strong "something went wrong"
    audio signature the way a cheer is a strong "something good happened"
    signature) - treat results as worth a look, not confirmed mistakes.
    """
    relative, duration, window_seconds = _compute_relative_energy(video_filename, window_seconds)
    if relative is None:
        return "No audio track found in this video; can't detect audio-based moments."
    if duration <= lead_seconds + trail_seconds:
        return "Video is too short for this kind of detection."

    min_rally_windows = max(1, int(min_rally_seconds / window_seconds))
    quiet_check_windows = max(1, int(quiet_check_seconds / window_seconds))

    is_active = relative >= active_threshold_db

    # Find runs of consecutive "active" (in-play) windows long enough to be
    # a real rally, not just a stray noise.
    candidates = []
    i = 0
    n = len(is_active)
    while i < n:
        if not is_active[i]:
            i += 1
            continue
        run_start = i
        while i < n and is_active[i]:
            i += 1
        run_end = i  # exclusive
        run_len = run_end - run_start
        if run_len < min_rally_windows:
            continue
        # Does a cheer-level spike happen shortly after this rally ends?
        check_end = min(n, run_end + quiet_check_windows)
        post = relative[run_end:check_end]
        had_reaction = len(post) > 0 and np.max(post) >= cheer_threshold_db
        if not had_reaction:
            end_time = run_end * window_seconds
            # Score by how abruptly it went quiet - bigger drop is a more
            # convincing "this fizzled out" moment.
            tail = relative[max(run_start, run_end - 2):run_end]
            drop = float(np.mean(tail)) if len(tail) else 0.0
            candidates.append((end_time, drop))

    if not candidates:
        return ("No clear quiet-rally-endings found - this video may not have "
                "distinct enough rally/silence contrast to detect.")

    candidates.sort(key=lambda c: c[1], reverse=True)
    selected = []
    for t, score in candidates:
        if all(abs(t - st) >= min_gap_seconds for st, _ in selected):
            selected.append((t, score))
        if len(selected) >= top_n:
            break

    if not selected:
        return ("No clear quiet-rally-endings found - this video may not have "
                "distinct enough rally/silence contrast to detect.")

    selected.sort(key=lambda c: c[0])

    lines = []
    for idx, (t, score) in enumerate(selected, start=1):
        start = max(0.0, t - lead_seconds)
        end = min(duration, t + trail_seconds)
        lines.append(
            f"{idx}. [{_format_srt_time(start)}-{_format_srt_time(end)}] "
            f"Possible learning moment (rally ended quietly around {_format_srt_time(t)}, "
            f"no crowd reaction detected - verify by watching)"
        )
    return "\n".join(lines)
