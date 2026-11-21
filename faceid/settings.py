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
    "MIN_SHARPNESS": 30.0,           # variance of the Laplacian; see the diagnostics page to calibrate
    "TOLERANCE": 0.6,                # largest Face Distance that counts as the same person
}


def apply_defaults(config: dict) -> None:
    for key, value in DEFAULTS.items():
        config.setdefault(key, value)
