"""VideoFileSource, and the real engine with the PresenceTracker on a clip (DESIGN: adapter tests).

The clip is made at test time from the public-domain portraits, so no video is committed.
A still photo never blinks, so the face is identified but never marked: exactly what a printed photo should get.
"""

import time
from pathlib import Path

import cv2
import pytest

from faceid.camera import CameraUnavailable, VideoFileSource
from faceid.presence import PresenceRules, PresenceTracker
from faceid.vision import DlibEngine

FACES = Path(__file__).parent / "fixtures" / "faces"
RULES = PresenceRules(tolerance=0.6, confirmation_frames=3, ear_threshold=0.25, blink_frames=1)


def make_clip(path, photo_names, frames_each=4, size=(640, 640)):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10.0, size)
    for name in photo_names:
        photo = cv2.resize(cv2.imread(str(FACES / f"{name}.jpg")), size)
        for _ in range(frames_each):
            writer.write(photo)
    writer.release()
    return str(path)


def play(path):
    source = VideoFileSource(path, realtime=False)
    frames = []
    while (frame := source.read()) is not None:
        frames.append(frame)
    source.close()
    return frames


def test_a_video_file_plays_every_frame_then_ends(tmp_path):
    frames = play(make_clip(tmp_path / "clip.avi", ["obama_2012", "biden_2013"]))

    assert len(frames) == 8
    assert frames[0].shape == (640, 640, 3)


def test_a_missing_video_file_is_reported():
    with pytest.raises(CameraUnavailable, match="could not be opened"):
        VideoFileSource("no-such-clip.avi")


def test_a_video_plays_at_its_own_speed(tmp_path):
    source = VideoFileSource(make_clip(tmp_path / "clip.avi", ["obama_2012"], frames_each=4))
    started = time.monotonic()
    while source.read() is not None:
        pass

    assert time.monotonic() - started >= 0.3  # 4 frames at 10 per second


def test_the_real_engine_identifies_the_enrolled_face_and_waits_for_a_blink(tmp_path):
    engine = DlibEngine()
    biden_2013 = cv2.imread(str(FACES / "biden_2013.jpg"))
    biden = engine.encode(biden_2013, engine.detect(biden_2013)[0])
    tracker = PresenceTracker({7: [biden]}, RULES)

    states = []
    for frame in play(make_clip(tmp_path / "clip.avi", ["biden_2021"], frames_each=4)):
        result = tracker.observe(engine.detect(frame), lambda face: engine.encode(frame, face))
        assert result.newly_confirmed == []
        states.append([(a.student_id, a.state) for a in result.annotations])

    assert states[-1] == [(7, "waiting")]


def test_the_real_engine_labels_a_stranger_unknown(tmp_path):
    engine = DlibEngine()
    biden_2013 = cv2.imread(str(FACES / "biden_2013.jpg"))
    tracker = PresenceTracker({7: [engine.encode(biden_2013, engine.detect(biden_2013)[0])]}, RULES)

    for frame in play(make_clip(tmp_path / "clip.avi", ["obama_2012"], frames_each=4)):
        result = tracker.observe(engine.detect(frame), lambda face: engine.encode(frame, face))

    assert [(a.student_id, a.state) for a in result.annotations] == [(None, "unknown")]
