# FaceID module design

How the code is divided into modules, and where the seams are. Words are from [`GLOSSARY.md`](../GLOSSARY.md); requirements (F*, N*) are from [`SPEC.md`](SPEC.md).

## Principle

The hard rules (who gets marked, when, how much credit) live in **plain Python modules that never touch the camera, dlib or MySQL**. Those modules take data in and return data out, so the tests run in milliseconds and the rules can be explained in a viva by reading one file. The camera, dlib, MySQL and Flask sit at the edges and stay thin.

```
            web (Flask blueprints)          cli (flask commands)
                 │        │        │              │
     ┌───────────┘        │        └──────┐       │
     ▼                    ▼               ▼       ▼
  live ──────────►  presence        reports    evaluation
   │  │              (pure)          │   │        │
   │  └──► enrolment (pure)          │   │        │
   │                                 │   │        │
   ├──► camera  ◄─── seam ───►  video file adapter (tests, evaluation)
   ├──► vision  ◄─── seam ───►  scripted fake (tests)
   └──► store (MySQL) ◄──────────────┘   └──► attendance (pure rules)
```

## Modules

All code lives in the `faceid/` package.

### `faceid/attendance.py`: attendance rules (pure)

The interface is three functions:

- `status_for(recognised_at, session, late_threshold) -> (status, minutes_late)`: returns Present or Late, and the minutes late.
- `credit(record, session) -> float`: the Attendance Credit for one record (ADR 0005).
- `percentage(records, held_sessions) -> float`: the Attendance Percentage.

These hold every rule from F5.3 and F5.7. Reports, live marking and Manual Override all call them, so a rule is never re-implemented elsewhere.

### `faceid/presence.py`: who is present in this frame (pure)

This is the deepest module, holding the recognition logic behind O2 and O4.

```python
tracker = PresenceTracker(gallery, settings)  # gallery: {student_id: [encodings]}
result = tracker.observe(faces, encode)       # faces: list[DetectedFace] (box + eye landmarks) from vision
                                              # encode: callable(face) -> 128-d encoding, called only when needed
result.annotations       # box, label, state for each face: unknown / waiting-for-blink / marked
result.newly_confirmed   # [(student_id, face_distance)] that just met F4.3
```

Inside it:
- Following each face from frame to frame by box overlap. A face is encoded only while it isn't yet identified. Encoding costs about 0.1 s per face, so encoding every face in every frame would drop 10 faces to about 1 frame per second, as the spike showed.
- Nearest-encoding matching within the Tolerance.
- The count of consecutive matching frames per Student.
- The Eye Aspect Ratio history and the Blink state machine per Student.
- Remembering who is already confirmed, so a Student is confirmed only once.

It has no clock, no IO and no dlib. Tests feed it scripted `DetectedFace` lists frame by frame, for example "matches Asha for 2 frames, then blinks, then matches 1 more frame", and check exactly when she is confirmed.

### `faceid/enrolment.py`: is this Capture acceptable (pure)

```python
assess_capture(frame, engine, others, rules) -> Accepted(encoding) | Rejected(reason)
draft = drafts.get(owner, student_id)           # DraftStore: one draft per browser login and Student
draft.capture(pose, frame, engine, others, rules) -> Accepted | Rejected
draft.ready_to_save(others, rules) -> [5 encodings] | Rejected
```

`assess_capture` holds every rejection rule in F3.2 and asks the engine for the cheap checks before the expensive encoding. `others` maps other active Students' display names to their encodings. `EnrolmentDraft` keeps the five poses in memory and re-checks them against other Students before they are saved.

### `faceid/matching.py`: comparing encodings (pure)

`face_distance(a, b)` and `nearest(encoding, gallery)`. Both Face Enrolment and live recognition use them, so matching has one definition.

### `faceid/vision.py`: the face engine (seam, two adapters)

```python
class FaceEngine(Protocol):
    def detect(self, frame_bgr) -> list[DetectedFace]          # box + eye landmarks (cheap)
    def sharpness(self, frame_bgr, face) -> float               # blur measure (cheap)
    def encode(self, frame_bgr, face: DetectedFace) -> encoding  # 128-d (expensive)
```

- **`DlibEngine`**, the real engine: it wraps `face_recognition` and handles downscaling, HOG or CNN detection, and landmark extraction. It is the only file that imports `face_recognition` or `dlib`. Calls into dlib take turns behind a lock, because Flask serves pages on several threads.
- **`ScriptedEngine`** (`tests/fakes.py`), for tests: it returns pre-set faces.

The app holds one engine in `app.extensions["face_engine"]`. Tests pass `FACE_ENGINE` in the config to replace it.

### `faceid/camera.py`: where frames come from (seam, two adapters)

```python
class FrameSource(Protocol):
    def read(self) -> frame | None
    def close(self)
```

- **`WebcamSource`**: OpenCV, using `CAP_DSHOW` on Windows and `CAP_V4L2` on Linux.
- **`VideoFileSource`**: plays a recorded clip. The classroom evaluation (§7.2) and end-to-end tests use it, so the same pipeline runs without a webcam.

### `faceid/live.py`: the running Class Session

```python
live = LiveSession(source, engine, store, settings)
live.start(session_id)    # loads gallery of Expected Students, starts threads (F4.6)
live.latest_jpeg()        # annotated frame for the MJPEG stream
live.status()             # marked / expected counts, per-student states
live.stop()
```

One capture thread keeps the latest frame. One recognition thread does three things in a loop: `engine.detect` → `tracker.observe` (which calls `engine.encode` only for unidentified faces) → for each newly confirmed Student, `attendance.status_for` and `store.mark`. This is the only module with threads, and the server holds one `LiveSession` because there is one camera (ADR 0004).

### `faceid/store/`: MySQL persistence

Plain SQL through mysql-connector-python, with no ORM, so the queries match the synopsis's tables one to one. It is split by area:

| File | Holds |
|---|---|
| `db.py` | Connection, transactions, migrations runner |
| `people.py` | Admin, Faculty, Student and Face Encoding rows |
| `teaching.py` | Subjects and Class Sessions |
| `attendance.py` | Opening (creating absent records), marking, Manual Override, closing |
| `queries.py` | Read-only report queries |

The store is tested against a real MySQL 8.0.46 in a podman container, never a fake. There is only one adapter, so a fake would test nothing real.

Schema changes are numbered files in `faceid/store/migrations/NNNN_*.sql`.

### `faceid/reports/`: building and exporting reports

```python
table = build(kind, params, store)   # -> Table(title, columns, rows), using attendance.percentage
data  = render(table, "xlsx" | "pdf" | "csv")  # -> bytes
```

There is one `Table` shape and three renderers, so all formats contain the same rows by construction (F6.2).

### `faceid/registration.py`: Registration form rules (pure)

`clean_student`, `clean_faculty` and `clean_subject` each return `(values, errors)` for one submitted form (F2.2). Uniqueness is left to the database's unique keys, plus `people.email_owner` for emails across roles.

### `faceid/feed.py`: one shared camera

`CameraFeed.latest_frame()` opens the camera on first use, keeps the newest frame from a background thread, and releases the camera after 15 s without requests. The app holds one in `app.extensions["camera_feed"]`. Tests pass `CAMERA_SOURCE` to use a still camera. `LiveSession` will read from it too.

### `faceid/preview.py`: live preview

`mjpeg_preview(feed, engine, rules)` streams annotated frames (face boxes with width and sharpness), at most 15 per second, to the diagnostics and enrolment pages.

### `faceid/web/`: Flask (thin)

The app factory plus blueprints `auth`, `admin`, `faculty`, `student`, `live` and `reports`, with Jinja templates and Bootstrap 5.

A view parses the request, checks the role, calls one module, then renders a template. Rules never live in views.

### `faceid/cli.py`: commands

`create-admin`, `db-upgrade`, `backup`, `restore` and `evaluate`.

Backup and restore are written in Python (JSON for each table), not with `mysqldump`, so they work on Windows without extra steps.

### `faceid/evaluation.py`: accuracy (§7)

- **LFW pairs**: through `DlibEngine`.
- **Classroom clip**: through `VideoFileSource` → `PresenceTracker`, so it measures the exact code that runs in class.

### `faceid/settings.py`: settings

Defaults for every setting in F4.5, overridden by `instance/config.py`. The `instance/` folder is untracked and holds the secret key and database password.

## Tests

| Kind | What | Where it runs |
|---|---|---|
| Unit | `attendance`, `presence`, `enrolment`, `reports.render` through their interfaces | anywhere, instant |
| Integration | `store`, web views (Flask test client) against real MySQL | Linux, podman MySQL |
| Adapter | `DlibEngine` on public-domain sample faces, `VideoFileSource` on a tiny clip | Linux |
| Manual | `docs/windows-checklist.md` | demo laptop, each release |
