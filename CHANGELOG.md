# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-11-24

### Added

- Reports for the Admin and Faculty: subject-wise, student-wise, date-wise, monthly summary and defaulter list. Each can be viewed in the browser and downloaded as Excel (.xlsx), PDF and CSV, with the same rows in every format.
- Attendance Percentage counts closed Class Sessions only, with partial credit for Late (ADR 0005, ADR 0008). Each Student's Held count is the closed Class Sessions they were Expected at.
- Faculty see reports on the Class Sessions they held, even after a Subject is reassigned. The Defaulter Threshold defaults to 75% and can be changed on the form.
- Students get a "My attendance" page with their own student-wise report (downloadable) and Class Session history.
- `flask backup <file>` and `flask restore <file>`, plus `backup.bat` and `restore.bat` on Windows. A backup holds every row, Face Encodings included, as one JSON file. Restore asks first, refuses a backup for a different schema, and changes nothing if any row fails to load.

### Security

- Names that a spreadsheet would run as formulas stay plain text in the xlsx and CSV files.

## [0.3.1] - 2026-11-24

### Fixed

- The Attendance Records table on an open Class Session's page now updates as Students are marked, instead of only after the page is reloaded. A Manual Override being edited is left alone until it is saved.

## [0.3.0] - 2026-11-22

### Added

- Class Sessions: a Faculty member starts a Class Session for one of their Subjects, which opens it with an absent Attendance Record for each Expected Student and turns the camera on. Only one Class Session can be open at a time.
- Live recognition: each face is followed from frame to frame and encoded only until it is identified. A Student is marked once their face has matched in 3 consecutive frames and blinked while matching; the face is checked once more at the blink, so swapping a photo and a live face can't mark anyone. The live view colours each face red (unknown), amber (waiting for a blink) or green (marked), beside a running "marked / expected" count.
- Students recognised more than 10 minutes after the start time are marked Late, with the minutes late. Attendance Credit and Attendance Percentage rules for reports, with partial credit for Late (ADR 0005).
- Closing a session leaves unmarked Students absent. Cancelling an open session removes it from everyone's attendance.
- Manual Override of any record in an open or closed session, including Late with minutes. The camera never changes a record set by hand.
- Students enrolled during an open session are recognised without restarting it. The session page lists Expected Students who aren't enrolled.
- Opening an open session's page after a server restart resumes recognition, on the same day only. A mark that fails to save is retried.
- `VideoFileSource` plays a recorded clip in place of the webcam, for tests and the classroom evaluation.
- Settings for Confirmation Frames, the Eye Aspect Ratio threshold, the Blink frame count and the Late Threshold.

### Changed

- The Faculty home page is the list of their Class Sessions.

## [0.2.0] - 2026-11-21

### Added

- Face Enrolment: the Admin enrols a Student from five guided Captures (front, left, right, chin up, chin down) with a live camera preview. Each Capture becomes a 128-number Face Encoding and the picture is discarded immediately; nothing is saved until all five are captured.
- Captures are refused, with the reason shown, when there is no face, more than one face, the face is too small or blurred, or it matches another enrolled Student.
- Re-enrolling replaces a Student's encodings in one transaction. The Student list shows who is enrolled.
- The live preview, on both the enrolment and diagnostics pages, labels each face with its width and sharpness.
- Each browser login keeps its own enrolment draft, forgotten after 30 minutes untouched. Saving re-checks the faces against Students enrolled in the meantime.
- Deactivated Students can't be enrolled, and their faces don't block other Students.

### Changed

- The webcam is shared between pages through one camera feed. It is released after 15 seconds unused and when the server stops, which fixes a crash on Ctrl+C. Captures only ever use a frame less than a second old, and the last frame is dropped when the camera is released.
- Calls into dlib take turns, because pages are served on several threads.
- `flask create-admin` reports a taken username clearly, without a traceback.

## [0.1.0] - 2026-11-21

First build for the demo laptop. It proves the stack (dlib, webcam, MySQL) works there.

### Added

- Accounts for Admin, Faculty and Students. Admin and Faculty log in by email, Students by Enrolment Number. Passwords are stored as bcrypt hashes, temporary passwords must be changed at first login, and changing a password needs the current one.
- `flask create-admin` creates the first Admin. There is no default account.
- Registration screens for the Admin: add, edit, deactivate and reactivate Students, Faculty and Subjects; reset a Student's password. Validation messages appear next to their fields. An email belongs to one account across all roles.
- `flask db-upgrade` builds the schema: the synopsis's seven tables with the changes in SPEC §4. Pages answer 503 until the schema is current.
- A camera diagnostics page shows the live webcam with face boxes, eye landmarks and processing speed.
- Windows setup: `setup.bat`, `run.bat` and `docs/windows-checklist.md`.
- A CSRF token on every form, and a secret key generated on first run.
- Bootstrap 5.3.9 is stored in the repo, so the app works offline.
- Planning documents: specification, module design, glossary, ADRs 0001–0006, stack research, and the camera spike findings.

[Unreleased]: https://github.com/Paragraph1148/FaceID/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/Paragraph1148/FaceID/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/Paragraph1148/FaceID/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/Paragraph1148/FaceID/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Paragraph1148/FaceID/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Paragraph1148/FaceID/releases/tag/v0.1.0
