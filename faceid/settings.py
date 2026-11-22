"""Default settings (SPEC F4.5). Any of them can be overridden in `instance/config.py`."""

DEFAULTS = {
    # Camera (ADR 0004). MJPG is requested because most webcams deliver only ~10 fps at 720p uncompressed.
    "CAMERA_INDEX": 0,
    "CAMERA_WIDTH": 1280,
    "CAMERA_HEIGHT": 720,
    # Detection. HOG needs faces of about 80 px; upsampling once halves that at about 4x the cost.
    "DETECTOR": "hog",               # "hog" or "cnn" (cnn is CPU-only with the prebuilt dlib: slow)
    "DETECTION_SCALE": 1.0,          # resize factor applied before detection
    "DETECTION_UPSAMPLE": 0,
    # Face Enrolment (F3.2) and matching (F4.2)
    "MIN_FACE_WIDTH": 80,            # px
    "MIN_SHARPNESS": 30.0,           # variance of the Laplacian; provisional until calibrated on the demo laptop
    "TOLERANCE": 0.6,                # largest Face Distance at which two Face Encodings are the same Student
    # Live recognition (F4.3) and marking (F5.3)
    "CONFIRMATION_FRAMES": 3,        # consecutive matching frames before a Student can be marked
    "EAR_THRESHOLD": 0.25,           # Eye Aspect Ratio below this is a closed eye (the spike measured 0.28-0.43 open)
    "BLINK_FRAMES": 1,               # frames the eyes must stay closed to count as a Blink
    "LATE_THRESHOLD_MINUTES": 10,
}


def apply_defaults(config: dict) -> None:
    for key, value in DEFAULTS.items():
        config.setdefault(key, value)
