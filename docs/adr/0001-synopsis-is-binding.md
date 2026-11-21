---
status: accepted
---

# The approved synopsis is the binding specification

The project synopsis approved by the guide (kept privately in `docs/private/`, a summary of its requirements is in `docs/SPEC.md`) binds the project on three levels: features and objectives, named algorithms (HOG detection, 128-d encodings, Euclidean matching, Eye Aspect Ratio blinks), and technology stack (Python 3.10, Flask 3, MySQL 8.0, OpenCV, dlib, face_recognition, Bootstrap 5). Examiners assess the delivered system against it, so v1.0.0 must implement all of it, and every deviation needs its own ADR so the report can list it.

## Considered Options

- **Rust + GPUI desktop app** (the original idea): faster and offline, but it contradicts the synopsis's stack, web interface and LAN dashboard, and nobody in the group knows Rust well enough to defend the code in a viva.
- **Same features in a newer stack**: rejected for the same reason: the stack is part of what was approved.

## Consequences

- Python 3.10 (end of life October 2026) and MySQL 8.0 (end of life April 2026) are used even though they no longer receive security fixes. Acceptable for a local, offline college demo. The report lists it as a limitation.
- Additions beyond the synopsis (such as the optional Spoof Check) are allowed when they don't replace a synopsis feature.
