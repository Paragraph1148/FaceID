# FaceID specification

Version 1.0 of this spec (2026-11-21). The words are defined in [`GLOSSARY.md`](../GLOSSARY.md). The approved synopsis is binding ([ADR 0001](adr/0001-synopsis-is-binding.md)). This document restates its requirements and adds what the grilling session decided. Where they differ, an ADR explains why.

## 1. Goal

Replace roll-call with a contactless system. A Faculty member opens a Class Session, the laptop webcam watches the class, and every Expected Student who is recognised and passes the Liveness Check is marked Present or Late. Everyone else is marked Absent when the session is closed. Attendance is then reported per Subject, per Student, per date and per month, and exported to Excel, PDF and CSV.

**Synopsis objectives (all required for v1.0.0):**

| # | Objective | Where met |
|---|---|---|
| O1 | Face-recognition attendance with Python and open-source CV libraries | §3 stack |
| O2 | Recognise multiple Students in one frame | §5.4 |
| O3 | Record attendance against Subject, Faculty, date and period automatically | §5.3, §5.5 |
| O4 | Prevent proxy attendance with recognition plus blink liveness | §5.4 |
| O5 | Role-based access for Admin, Faculty and Student through a web interface | §5.1 |
| O6 | Subject-wise, student-wise and date-wise reports, exported to Excel and PDF | §5.6 |
| O7 | At least 90% recognition accuracy under normal classroom lighting | §6, §7 |

**Out of scope (from the synopsis):**
- Masked or helmeted faces
- Very low-resolution or very dark scenes
- Integration with a university ERP

## 2. Users and deployment

- One Flask server runs on the Faculty laptop. The demo machine is a Windows 11 x64 gaming laptop.
- That laptop's webcam is the only camera ([ADR 0004](adr/0004-camera-on-the-server.md)).
- The server listens on the local network. Any browser on the LAN can use the dashboards and reports. Only the server laptop's camera takes attendance.
- Development happens on Fedora Linux, and Linux is where the automated tests run.
- Windows is checked by hand on the demo laptop, using `docs/windows-checklist.md`, at every release.

## 3. Stack (binding)

| Concern | Choice | Version |
|---|---|---|
| Language | Python | 3.10 |
| Web | Flask, Flask-Login, Jinja templates, Bootstrap 5, vanilla JS | Flask 3.1.3, Flask-Login 0.6.3 |
| Database | MySQL via mysql-connector-python | 8.0.46, connector 26.10.0 |
| Vision | OpenCV, dlib (`dlib-bin` prebuilt), face_recognition, imutils | see `requirements.txt` |
| Maths | NumPy, SciPy | 2.2.6, 1.15.3 |
| Reports | Pandas, openpyxl, ReportLab | 2.3.3, 3.1.5, 5.1.0 |
| Passwords | bcrypt | 5.0.0 |
| Tests | pytest | 9.2.0 |

The pinned list and the install quirks come from [the stack research](research/2026-11-21-stack-facts.md):
- `face_recognition` is installed with `--no-deps`.
- `setuptools` stays below 82.
- dlib is CPU-only.

## 4. Data model

The synopsis's seven tables (`admin`, `student`, `face_encoding`, `faculty`, `subject`, `class_session`, `attendance`) are kept, with their columns, types and constraints, except for these changes:

| Change | Why |
|---|---|
| `face_encoding.image_path` removed | [ADR 0002](adr/0002-no-face-images-stored.md): no face images stored |
| `student.password_hash`, `student.must_change_password` added | [ADR 0003](adr/0003-student-password-column.md): Student login |
| `faculty.must_change_password` added | Faculty accounts are created by the Admin with a temporary password |
| `subject.course` added | [ADR 0006](adr/0006-subjects-belong-to-a-programme.md): Expected Students |
| `attendance.minutes_late` added (INT NULL) | [ADR 0005](adr/0005-late-earns-partial-credit.md): partial credit |

Other rules:
- `attendance` has UNIQUE (`session_id`, `student_id`), as in the synopsis.
- `face_encoding.encoding_vector` stores 128 little-endian float64 values (1024 bytes).
- Schema changes are applied by numbered SQL migration files. The app refuses to start on an outdated schema.

## 5. Functional requirements

### 5.1 Accounts and roles

- **F1.1**: There are three roles: Admin, Faculty and Student.
  - Admin and Faculty log in with their email address.
  - Students log in with their Enrolment Number.
  - Passwords are stored only as bcrypt hashes.
- **F1.2**: `flask create-admin` creates an Admin interactively from the command line. There is no default account and no password in the repo.
- **F1.3**: Accounts created by the Admin start with a temporary password and must change it at first login:
  - A Student's temporary password is their Enrolment Number.
  - A Faculty member's is set by the Admin.
- **F1.4**: Every page checks the role.
  - A Student can see only their own records.
  - A Faculty member can run sessions only for their own Subjects.

### 5.2 Registration (Admin)

- **F2.1**: The Admin can create, edit and deactivate Students, Faculty and Subjects. Records are deactivated, never deleted. A deactivated Student is no longer an Expected Student, and their past records remain.
- **F2.2**: Field validation:
  - Enrolment Numbers, Subject Codes and emails are unique.
  - Semester is between 1 and 12.
  - Validation errors are shown next to the field they belong to.

### 5.3 Face Enrolment (Admin)

- **F3.1**: The Admin enrols a Student from 5 guided Captures: front, turned left, turned right, chin up, chin down.
- **F3.2**: A Capture is rejected, with a reason shown, if any of these is true:
  - It contains zero faces or more than one face.
  - The face is narrower than 80 px.
  - The image is blurred (variance of the Laplacian below a set threshold).
  - It matches a *different* Student within the Tolerance. This rejection names the other Student.
- **F3.3**: Each accepted Capture becomes one Face Encoding. The image is discarded in memory and never written to disk or the database.
- **F3.4**: Re-enrolling a Student replaces all of their Face Encodings in one transaction.

### 5.4 Live recognition

- **F4.1**: While a Class Session is open, the server reads frames from the webcam (DirectShow on Windows, V4L2 on Linux), requesting MJPG at 1280×720.
  - It runs HOG detection on every processed frame at full resolution and follows each face from frame to frame.
  - A followed face is encoded until it is identified (or labelled Unknown), and compared with the cached encodings of that session's Expected Students. After that, only its eye landmarks are read each frame.
  - Encoding is the expensive step, about 0.1 s per face on the development laptop, so only faces still being identified are encoded.
  - The detector is a setting: `hog` (default) or `cnn`.
- **F4.2**: A face matches the Student with the smallest Face Distance, if that distance is ≤ the Tolerance (default 0.6). Otherwise it's labelled "Unknown".
- **F4.3**: A Student is **marked** only when all three of these hold:
  1. They matched in the Confirmation Frames number of consecutive processed frames (default 3).
  2. A Blink was seen on their face during the session. Blink means: the Eye Aspect Ratio, averaged over both eyes using the 6-point eye landmarks, falls below 0.25 for at least 1 processed frame and then rises back above it.
  3. If the Spoof Check is enabled, it passes.
- **F4.4**: The browser shows the live feed with a box and name on each face, coloured by state: unknown, matched but waiting for a blink, or marked. Beside it is a running "marked / expected" count.
- **F4.5**: Tolerance, Confirmation Frames, the EAR threshold, the blink frame count, the detection scale and upsampling, the detector and the Late Threshold are all settings in one config file. None of them is hard-coded.
- **F4.6**: Encodings for the session's Expected Students are loaded into memory once when the session opens, as the synopsis's "cached at startup" requires. They are reloaded if Face Enrolment changes during a session.

### 5.5 Class Sessions and attendance marking (Faculty)

- **F5.1**: A Faculty member creates a Class Session for one of their Subjects with a date, start time, end time and optional room number.
- **F5.2**: Opening a session:
  - Creates one Attendance Record per Expected Student, with status `absent` and method `face`.
  - Fails if the server already has an open session (one camera).
- **F5.3**: When a Student is marked, their record changes as follows:
  - Recognised at or before start time + Late Threshold (default 10 minutes): becomes `present`.
  - Recognised later: becomes `late`, with `minutes_late` set.
  - `marked_at` and `confidence` (= 1 − Face Distance) are recorded.
  - A Student already marked is never marked again: the first recognition wins.
- **F5.4**: The session keeps scanning until the Faculty presses **Close**. Closing makes the remaining `absent` records final, and a closed session can't be reopened.
- **F5.5**: Cancelling a session sets its status to `cancelled`. Cancelled sessions count towards nobody's Attendance Percentage.
- **F5.6**: A Faculty member can apply Manual Override to any record of their own sessions, open or closed:
  - The status is set to `present`, `late` or `absent`, and the method to `manual`.
  - If the override is `late`, the Faculty enters the minutes late.
- **F5.7**: Attendance Credit: Present = 1, Absent = 0, and Late = (session length − minutes late) / session length, floored at 0. Attendance Percentage = Σ credit / number of held sessions × 100.

### 5.6 Reports

- **F6.1**: The reports are:
  - Subject-wise: each Student's Attendance Percentage in one Subject.
  - Student-wise: one Student's Attendance Percentage in each of their Subjects.
  - Date-wise: every record of every session on a date.
  - Monthly summary: each Subject × Student for one calendar month.
  - Defaulter list: Students below the Defaulter Threshold (default 75%) in a Subject.
- **F6.2**: Every report can be viewed in the browser and downloaded as **.xlsx, PDF and CSV**. All three formats contain the same rows.
- **F6.3**: Who sees which reports:
  - Admin: all reports.
  - Faculty: reports for their own Subjects.
  - Student: only their own student-wise report and session history.

### 5.7 Operations

- **F7.1**: `flask db-upgrade` applies migrations.
- **F7.2**: `flask backup <file>` and `flask restore <file>` dump and load the database. That covers encodings, so pre-enrolled demo data survives reinstalls.
- **F7.3**: `flask evaluate` runs the accuracy evaluation in §7.

## 6. Non-functional requirements

- **N1, speed**: measured on the demo laptop:
  - The live view runs at 20 frames per second or more.
  - With up to 10 already-identified faces in frame, recognition processes at least 5 frames per second.
  - A new face is identified within 1 second of appearing.
  - Capture and recognition run in separate threads, which stop cleanly when the session or server stops.
- **N2, accuracy**: identification rate of at least 90% on the classroom evaluation in §7.2, and no wrong-Student marks in it.
- **N3, privacy**: no face images are stored anywhere (F3.3). The database and backups contain encodings only.
- **N4, platforms**:
  - Windows 11 x64 is the demo platform and must pass `docs/windows-checklist.md`.
  - Fedora Linux is the development and test platform.
- **N5, offline**: once installed, the app makes no internet calls.
- **N6, security**:
  - Passwords are stored as bcrypt hashes.
  - Forms are protected by CSRF tokens.
  - The secret key is generated on first run into an untracked instance folder.
  - Nothing secret is committed.
- **N7, explainability**: each module has a plain-English explainer in `docs/modules/` that the team member responsible for it can study for the viva.

## 7. Accuracy evaluation

1. **LFW**: verification accuracy of the encoding model on LFW's `pairs.txt` 10-fold protocol, read from the raw JPEGs. The best Tolerance found is reported next to the default 0.6. The dataset is downloaded once from the scikit-learn figshare mirror. It's cited as a benchmark only, since its licence couldn't be verified.
2. **Classroom clip**: the three team members are enrolled, then recorded with the demo laptop's webcam at roughly 1 m, 2.5 m and 4 m, in normal and dim light. Reported figures:
   - Identification rate per condition.
   - Count of wrong-Student marks.
   - Time to mark.

   The recording stays on the team's machines, outside git (N3).

`flask evaluate` prints both results as tables ready to paste into the report.

## 8. Milestones

Each milestone goes through a `feat/` branch, a PR, `code-review`, a merge to `main`, a `vX.Y.Z` tag, a changelog entry and a push. Dates assume a submission around 2026-12-21.

| Version | Target | Acceptance |
|---|---|---|
| **0.1.0** | Nov 28 | F1.\*, F2.\*, F7.1 work; the schema matches §4; a camera diagnostics page shows live HOG detection boxes and FPS; the Windows checklist passes on the demo laptop, which proves dlib, the webcam and MySQL work there |
| **0.2.0** | Dec 3 | F3.\* (Face Enrolment) |
| **0.3.0** | Dec 8 | F4.\* and F5.\* (live recognition, Blink, marking, Late, close, cancel, Manual Override) |
| **0.4.0** | Dec 13 | F6.\* (all reports, all three formats, Student view), F7.2 |
| **0.5.0** | Dec 16 | F7.3 and §7 results; N1 and N2 measured; optional Spoof Check |
| **1.0.0** | Dec 19 | Every objective in §1 met; N1–N7 verified; module explainers written; final Windows checklist run |

## 9. Known limitations (for the report)

- **Blink liveness**: it can be fooled by a video replay of the Student. The optional Spoof Check reduces this risk but doesn't remove it.
- **Software versions**: Python 3.10 and MySQL 8.0 are past end of life (ADR 0001).
- **CPU only**: the prebuilt dlib can't use a GPU, so CNN detection is slow.
- **Distance from the camera**: HOG needs a face about 80 px wide, or 40 px with upsampling at roughly 4× the cost. On a 720p laptop webcam that is about 1.7 m by default and about 3.5 m with upsampling. Students further back aren't detected. The synopsis's recommended 1080p webcam extends both distances by half. §7.2 measures the real limits.
- **Re-enrolment**: changing the encoding model means everyone must be enrolled again (ADR 0002).
