"""Audio-spike-based highlight detection.

FunClip's core workflow finds clips by matching text in the ASR transcript.
That doesn't work for footage with little or no dialogue to transcribe -
e.g. raw sports recordings, where the audio is mostly ambient/crowd noise
rather than speech (confirmed via ASR testing: both bundled models produce
garbage output on this kind of content, because there's genuinely little
speech there to recognize).

For that case, this looks for a different, more useful signal: sudden
spikes in audio energy - the crowd/players reacting to something happening,
which in practice tends to follow the actual highlight moment (a good
rally, a point scored) by a couple of seconds. It's a heuristic, not a
real understanding of gameplay, so results should be treated as candidates
to skim rather than a guaranteed-accurate highlight reel.
"""
import os
import logging

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


def detect_audio_highlights(video_filename, top_n=6, lead_seconds=8.0, trail_seconds=2.0,
                             min_gap_seconds=15.0, window_seconds=0.5):
    """Find candidate highlight moments by audio-energy spikes in a video.

    Returns text in the same "N. [start-end] label" format the LLM Clipping
    result box produces, so it can be fed straight into the existing AI Clip
    / AI Clip+Subtitles buttons without any other UI changes.
    """
    video = mpy.VideoFileClip(video_filename)
    if video.audio is None:
        return "No audio track found in this video; can't detect audio-based highlights."

    base_name, _ = os.path.splitext(video_filename)
    audio_file = base_name + '_highlight_tmp.wav'
    video.audio.write_audiofile(audio_file, logger=None)
    try:
        y, sr = librosa.load(audio_file, sr=16000, mono=True)
    finally:
        if os.path.exists(audio_file):
            os.remove(audio_file)

    duration = len(y) / sr
    if duration <= lead_seconds + trail_seconds:
        return "Video is too short for highlight detection."

    hop = int(window_seconds * sr)
    n_windows = max(1, len(y) // hop)
    energy = np.array([
        np.sqrt(np.mean(np.square(y[i * hop:(i + 1) * hop])))
        if len(y[i * hop:(i + 1) * hop]) else 0.0
        for i in range(n_windows)
    ])
    # dB-like scale (with a floor so silence doesn't produce -inf).
    energy_db = 20 * np.log10(energy + 1e-6)

    # Rolling local baseline so this finds spikes relative to this video's
    # own recent noise floor, not an absolute loudness threshold.
    baseline_windows = max(1, int(20.0 / window_seconds))  # ~20s of context
    baseline = np.array([
        np.median(energy_db[max(0, i - baseline_windows): i + 1])
        for i in range(len(energy_db))
    ])
    relative = energy_db - baseline

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
