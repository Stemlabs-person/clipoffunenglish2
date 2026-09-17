"""Jersey-number filtering for candidate clips.

FunClip's audio-based highlight/learning-moment detection (see
highlight_utils.py) finds *when* something interesting probably happened,
but has no idea *who* was involved - audio alone carries no player
identity. This adds a visual pass on top: given a jersey number, sample a
few frames from each already-detected candidate segment and use OCR to
check whether that number actually appears on screen there, keeping only
the segments where it does.

This is intentionally scoped down from real player tracking (the kind a
dedicated product like Tavo does, trained on tens of thousands of matches):
it only asks "does this number appear somewhere in this segment", not
"is this specific play about this specific player" - a teammate wearing
the same number in a background moment, or a scoreboard digit, could
still cause a false positive. Treat matches as candidates to confirm by
watching, not certainties.
"""
import re

import numpy as np
import moviepy.editor as mpy

_reader = None


def _get_reader():
    """Lazily create and cache the OCR reader (loading its models is slow -
    do it once per process, not once per frame)."""
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    return _reader


def _parse_segments(segments_text):
    """Pull (line, start_seconds, end_seconds) out of the numbered
    '[HH:MM:SS,mmm-HH:MM:SS,mmm]' lines detect_audio_highlights()/
    detect_learning_moments() produce."""
    pattern = re.compile(
        r'^(\d+)\.\s*\[(\d{2}):(\d{2}):(\d{2}),(\d{2,3})-(\d{2}):(\d{2}):(\d{2}),(\d{2,3})\]'
    )
    segments = []
    for line in segments_text.splitlines():
        m = pattern.match(line.strip())
        if not m:
            continue
        h1, m1, s1, ms1 = int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
        h2, m2, s2, ms2 = int(m.group(6)), int(m.group(7)), int(m.group(8)), int(m.group(9))
        start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0
        end = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0
        segments.append((line, start, end))
    return segments


_TEAM_LABEL_RE = re.compile(r'^[A-Z]{3,}$')


def _frame_has_number(detections, jersey_number):
    """Check one frame's OCR detections for the target number, using a
    nearby all-caps team-name-like label as a confidence boost (a real
    jersey has one printed above the number; a scoreboard/signage digit
    usually doesn't)."""
    number_boxes = [d for d in detections if d[1].strip() == jersey_number]
    if not number_boxes:
        return False, 0.0
    label_boxes = [d[0] for d in detections if _TEAM_LABEL_RE.match(d[1].strip())]
    best_conf = 0.0
    for bbox, text, conf in number_boxes:
        num_cy = (bbox[0][1] + bbox[2][1]) / 2
        num_cx = (bbox[0][0] + bbox[2][0]) / 2
        near_label = any(
            abs(((lb[0][0] + lb[2][0]) / 2) - num_cx) < 150
            and 0 < (num_cy - ((lb[0][1] + lb[2][1]) / 2)) < 150
            for lb in label_boxes
        )
        score = conf + (0.5 if near_label else 0.0)
        best_conf = max(best_conf, score)
    return True, best_conf


def filter_segments_by_jersey_number(video_filename, segments_text, jersey_number,
                                      samples_per_segment=4, min_confidence=0.5):
    """Keep only the candidate segments where `jersey_number` is visible.

    `segments_text` is the existing numbered highlight/learning-moment
    result text; returns the same format, filtered and renumbered.
    """
    jersey_number = str(jersey_number).strip()
    if not jersey_number:
        return segments_text
    if not jersey_number.isdigit():
        return "Jersey number should just be digits (e.g. 30), got: {!r}".format(jersey_number)

    segments = _parse_segments(segments_text)
    if not segments:
        return ("Couldn't find any [start-end] segments in the current results box - "
                "run Detect Highlights or Detect Learning Moments first.")

    video = mpy.VideoFileClip(video_filename)
    reader = _get_reader()

    kept = []
    for line, start, end in segments:
        if end <= start:
            continue
        sample_times = np.linspace(start, end, num=samples_per_segment + 2)[1:-1]
        found = False
        best = 0.0
        for t in sample_times:
            t = min(max(t, 0.0), video.duration - 0.01)
            frame = video.get_frame(t)  # RGB numpy array
            detections = reader.readtext(frame)
            hit, conf = _frame_has_number(detections, jersey_number)
            if hit:
                found = True
                best = max(best, conf)
        if found and best >= min_confidence:
            kept.append((line, best))

    if not kept:
        return (f"No segment showed jersey #{jersey_number} clearly enough "
                f"(checked {len(segments)} candidate segment(s)). Try a lower "
                f"number of samples/confidence, or this player may not be in "
                f"any detected segment.")

    lines = []
    for idx, (line, conf) in enumerate(kept, start=1):
        # Strip the old numbering, keep the rest of the line, renumber, and
        # note the OCR confidence for transparency about how sure this is.
        rest = line.split('.', 1)[1].strip() if '.' in line else line
        lines.append(f"{idx}. {rest} [jersey #{jersey_number} confidence: {conf:.2f}]")
    return "\n".join(lines)
