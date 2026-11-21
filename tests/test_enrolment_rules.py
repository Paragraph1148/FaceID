"""F3.2: when a Capture is accepted or rejected (faceid.enrolment, pure)."""

from fakes import ScriptedEngine, encoding, face, near

from faceid.enrolment import Accepted, EnrolmentRules, Rejected, assess_capture

RULES = EnrolmentRules(min_face_width=80, min_sharpness=40.0, tolerance=0.6)
FRAME = object()  # the scripted engine ignores the frame itself
RAVI = encoding(1)
OTHERS = {"Ravi Kumar (SSPU20260002)": [RAVI]}


def assess(*faces, others=OTHERS):
    engine = ScriptedEngine()
    engine.show(*faces)
    return assess_capture(FRAME, engine, others, RULES)


def test_a_single_clear_unknown_face_is_accepted_with_its_encoding():
    asha = encoding(2)

    result = assess(face(encoding=asha))

    assert isinstance(result, Accepted)
    assert (result.encoding == asha).all()


def test_no_face_is_rejected():
    assert assess() == Rejected("No face found. Look at the camera, in good light.")


def test_more_than_one_face_is_rejected():
    result = assess(face(left=100, encoding=encoding(2)), face(left=400, encoding=encoding(3)))

    assert result == Rejected("2 faces in view. Only the Student being enrolled may be in front of the camera.")


def test_a_face_narrower_than_the_minimum_is_rejected():
    result = assess(face(width=79, encoding=encoding(2)))

    assert result == Rejected("Face is too small (79 px, needs 80). Move closer to the camera.")


def test_a_blurred_capture_is_rejected():
    result = assess(face(encoding=encoding(2), sharpness=39.9))

    assert result == Rejected("The picture is blurred. Hold still and try again.")


def test_a_face_matching_another_enrolled_student_is_rejected_and_names_them():
    result = assess(face(encoding=near(RAVI, 0.59)))

    assert result == Rejected("This face matches Ravi Kumar (SSPU20260002), who is already enrolled.")


def test_a_face_just_beyond_the_tolerance_of_another_student_is_accepted():
    assert isinstance(assess(face(encoding=near(RAVI, 0.61))), Accepted)
