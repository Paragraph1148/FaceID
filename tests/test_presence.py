"""F4.2, F4.3: who is marked, and when (faceid.presence, pure).

Each test plays frames into a PresenceTracker. A frame is a list of DetectedFaces; `encode` returns the
encoding scripted for a face's position, the way the real engine would for that person.
"""

from fakes import encoding, near

from faceid.presence import PresenceRules, PresenceTracker
from faceid.vision import DetectedFace

RULES = PresenceRules(tolerance=0.6, confirmation_frames=3, ear_threshold=0.25, blink_frames=1)
ASHA, RAVI = 1, 2
GALLERY = {ASHA: [encoding(1)], RAVI: [encoding(2)]}

OPEN = ((0, 5), (3, 2), (6, 2), (9, 5), (6, 8), (3, 8))      # Eye Aspect Ratio 0.67
CLOSED = ((0, 5), (3, 5), (6, 5), (9, 5), (6, 5), (3, 5))    # Eye Aspect Ratio 0


def at(left, eyes=OPEN):
    """A 120 px face whose left edge is at `left`."""
    return DetectedFace(box=(100, left + 120, 220, left), left_eye=eyes, right_eye=eyes)


class Encoder:
    """Returns the encoding of whoever stands at each left position (within 30 px), and counts calls."""

    def __init__(self, people):
        self.people = people  # {left: encoding}
        self.calls = 0

    def __call__(self, face):
        self.calls += 1
        left = face.box[3]
        return next(enc for x, enc in self.people.items() if abs(x - left) <= 30)


def play(tracker, encoder, frames):
    """Observe each frame; return every Student confirmed along the way, and the last frame's annotations."""
    confirmed, result = [], None
    for frame in frames:
        result = tracker.observe(frame, encoder)
        confirmed += result.newly_confirmed
    return confirmed, result.annotations


def test_a_student_matching_for_the_confirmation_frames_who_blinks_is_confirmed_once():
    tracker = PresenceTracker(GALLERY, RULES)
    encoder = Encoder({100: near(encoding(1), 0.3)})

    confirmed, annotations = play(tracker, encoder, [[at(100)], [at(100, CLOSED)], [at(100)], [at(100)], [at(100)]])

    assert [(who, round(distance, 6)) for who, distance in confirmed] == [(ASHA, 0.3)]
    assert annotations[0].student_id == ASHA and annotations[0].state == "marked"


def test_without_a_blink_the_student_is_identified_but_never_marked():
    tracker = PresenceTracker(GALLERY, RULES)

    confirmed, annotations = play(tracker, Encoder({100: encoding(1)}), [[at(100)]] * 10)

    assert confirmed == []
    assert annotations[0].student_id == ASHA and annotations[0].state == "waiting"


def test_eyes_that_close_but_have_not_reopened_are_not_yet_a_blink():
    tracker = PresenceTracker(GALLERY, RULES)

    confirmed, _ = play(tracker, Encoder({100: encoding(1)}), [[at(100)]] * 3 + [[at(100, CLOSED)]] * 3)

    assert confirmed == []


def test_a_blink_needs_the_eyes_closed_for_the_blink_frame_count():
    tracker = PresenceTracker(GALLERY, PresenceRules(0.6, 3, 0.25, blink_frames=2))
    one_frame_blink = [[at(100)], [at(100, CLOSED)], [at(100)], [at(100)], [at(100)]]
    two_frame_blink = [[at(100, CLOSED)], [at(100, CLOSED)], [at(100)]]

    confirmed_after_short_blink, _ = play(tracker, Encoder({100: encoding(1)}), one_frame_blink)
    confirmed_after_long_blink, _ = play(tracker, Encoder({100: encoding(1)}), two_frame_blink)

    assert confirmed_after_short_blink == []
    assert [who for who, _ in confirmed_after_long_blink] == [ASHA]


def test_matches_must_be_consecutive():
    tracker = PresenceTracker(GALLERY, RULES)
    blink = [[at(100)], [at(100, CLOSED)]]
    gap = [[]]  # the detector missed the face in one frame

    confirmed, annotations = play(tracker, Encoder({100: encoding(1)}), blink + gap + [[at(100)]] * 2)

    assert confirmed == []
    confirmed, _ = play(tracker, Encoder({100: encoding(1)}), [[at(100)]])
    assert [who for who, _ in confirmed] == [ASHA]


def test_a_face_farther_than_the_tolerance_from_everyone_is_unknown():
    tracker = PresenceTracker(GALLERY, RULES)
    stranger = near(encoding(1), 0.61)

    confirmed, annotations = play(tracker, Encoder({100: stranger}), [[at(100)], [at(100, CLOSED)]] + [[at(100)]] * 5)

    assert confirmed == []
    assert annotations[0].student_id is None and annotations[0].state == "unknown"


def test_the_nearest_student_is_the_match():
    gallery = {ASHA: [encoding(1)], RAVI: [near(encoding(1), 0.5)]}
    tracker = PresenceTracker(gallery, RULES)

    confirmed, _ = play(tracker, Encoder({100: near(encoding(1), 0.1)}), [[at(100)], [at(100, CLOSED)], [at(100)], [at(100)]])

    assert [who for who, _ in confirmed] == [ASHA]


def test_an_identified_face_is_followed_as_it_moves_and_is_not_encoded_again():
    tracker = PresenceTracker(GALLERY, RULES)
    encoder = Encoder({100: encoding(1)})
    play(tracker, encoder, [[at(100)]] * 3)
    assert encoder.calls == 3

    _, annotations = play(tracker, encoder, [[at(110)], [at(120)], [at(125)]])

    assert encoder.calls == 3
    assert annotations[0].student_id == ASHA


def test_an_unknown_face_is_checked_again_only_every_tenth_frame():
    tracker = PresenceTracker(GALLERY, RULES)
    encoder = Encoder({100: encoding(9)})

    play(tracker, encoder, [[at(100)]] * 23)

    # Frames 1-3 decide it is unknown; it is checked again at frames 13 and 23.
    assert encoder.calls == 5


def test_two_students_in_view_are_followed_separately():
    tracker = PresenceTracker(GALLERY, RULES)
    encoder = Encoder({100: encoding(1), 600: encoding(2)})
    frames = [[at(100), at(600)], [at(100, CLOSED), at(600)], [at(100), at(600)], [at(100), at(600)]]

    confirmed, annotations = play(tracker, encoder, frames)

    assert [who for who, _ in confirmed] == [ASHA]
    assert {(a.student_id, a.state) for a in annotations} == {(ASHA, "marked"), (RAVI, "waiting")}


def test_a_student_is_confirmed_only_once_even_after_leaving_and_returning():
    tracker = PresenceTracker(GALLERY, RULES)
    visit = [[at(100)], [at(100, CLOSED)], [at(100)], [at(100)]]
    away = [[]] * 10

    confirmed, annotations = play(tracker, Encoder({100: encoding(1)}), visit + away + visit)

    assert [who for who, _ in confirmed] == [ASHA]
    assert annotations[0].state == "marked"


def test_students_already_marked_in_this_session_show_as_marked_and_are_not_confirmed_again():
    tracker = PresenceTracker(GALLERY, RULES, already_marked={ASHA})

    confirmed, annotations = play(tracker, Encoder({100: encoding(1)}), [[at(100)], [at(100, CLOSED)], [at(100)], [at(100)]])

    assert confirmed == []
    assert annotations[0].state == "marked"


def test_a_student_enrolled_during_the_session_is_recognised_at_once():
    tracker = PresenceTracker({ASHA: [encoding(1)]}, RULES)
    encoder = Encoder({100: encoding(2)})
    play(tracker, encoder, [[at(100)]] * 4)  # unknown so far

    tracker.replace_gallery(GALLERY)
    confirmed, annotations = play(tracker, encoder, [[at(100), ], [at(100, CLOSED)], [at(100)], [at(100)]])

    assert [who for who, _ in confirmed] == [RAVI]


# --- Review fixes: the Blink and the identity must come from the same face ---


def test_a_blink_by_someone_else_before_the_face_was_identified_does_not_count():
    # A stranger blinks, then a photo of Asha is held where their face was.
    tracker = PresenceTracker(GALLERY, RULES)
    encoder = Encoder({100: encoding(9)})
    play(tracker, encoder, [[at(100)], [at(100, CLOSED)], [at(100)]])

    encoder.people = {100: encoding(1)}
    confirmed, annotations = play(tracker, encoder, [[at(100)]] * 12)  # re-checked at frame 13, identified by 15

    assert confirmed == []
    assert annotations[0].state == "waiting"


def test_a_live_face_blinking_where_an_identified_photo_was_does_not_mark_the_photo():
    tracker = PresenceTracker(GALLERY, RULES)
    encoder = Encoder({100: encoding(1)})
    play(tracker, encoder, [[at(100)]] * 3)  # a photo of Asha, identified

    encoder.people = {100: encoding(9)}      # a stranger moves into the same place and blinks
    confirmed, _ = play(tracker, encoder, [[at(100, CLOSED)], [at(100)], [at(100)]])

    assert confirmed == []


def test_the_face_is_checked_once_more_when_it_blinks_before_confirming():
    tracker = PresenceTracker(GALLERY, RULES)
    encoder = Encoder({100: encoding(1)})
    play(tracker, encoder, [[at(100)]] * 3)

    confirmed, _ = play(tracker, encoder, [[at(100, CLOSED)], [at(100)]])

    assert [who for who, _ in confirmed] == [ASHA]
    assert encoder.calls == 4


def test_a_confirmation_that_could_not_be_saved_is_retried():
    tracker = PresenceTracker(GALLERY, RULES)
    encoder = Encoder({100: encoding(1)})
    confirmed, _ = play(tracker, encoder, [[at(100)], [at(100, CLOSED)], [at(100)]])
    assert [who for who, _ in confirmed] == [ASHA]

    tracker.unconfirm(ASHA)  # e.g. the database write failed
    confirmed, _ = play(tracker, encoder, [[at(100)]])

    assert [who for who, _ in confirmed] == [ASHA]
