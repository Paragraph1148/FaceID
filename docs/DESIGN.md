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
result = tracker.observe(faces)               # faces: list[DetectedFace] from vision
result.annotations       # box, label, state for each face: unknown / waiting-for-blink / marked
result.newly_confirmed   # [(student_id, face_distance)] that just met F4.3
```

Inside it:
- Nearest-encoding matching within the Tolerance.
- The count of consecutive matching frames per Student.
- The Eye Aspect Ratio history and the Blink state machine per Student.
- Remembering who is already confirmed, so a Student is confirmed only once.

It has no clock, no IO and no dlib. Tests feed it scripted `DetectedFace` lists frame by frame, for example "matches Asha for 2 frames, then blinks, then matches 1 more frame", and check exactly when she is confirmed.

### `faceid/enrolment.py`: is this Capture acceptable (pure)

```python
assess_capture(faces, sharpness, other_gallery, settings) -> Accepted(encoding) | Rejected(reason)
```

This holds every rejection rule in F3.2. The caller saves the returned encodings; it never sees an image.

### `faceid/vision.py`: the face engine (seam, two adapters)

```python
class FaceEngine(Protocol):
    def analyse(self, frame_rgb) -> list[DetectedFace]  # box, 128-d encoding, eye landmarks
    def sharpness(self, frame_rgb) -> float
```

- **`DlibEngine`**, the real engine: it wraps `face_recognition` and handles downscaling, HOG or CNN detection, and landmark extraction. It is the only file that imports `face_recognition` or `dlib`.
- **`ScriptedEngine`**, for tests: it returns pre-set faces.

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

One capture thread keeps the latest frame. One recognition thread does three things in a loop: `engine.analyse` → `tracker.observe` → for each newly confirmed Student, `attendance.status_for` and `store.mark`. This is the only module with threads, and the server holds one `LiveSession` because there is one camera (ADR 0004).

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

### `faceid/web/`: Flask (thin)

The app factory plus blueprints `auth`, `admin`, `faculty`, `student`, `live` and `reports`, with Jinja templates and Bootstrap 5.

A view parses the request, checks the role, calls one module, then renders a template. Rules never live in views.

### `faceid/cli.py`: commands

`create-admin`, `db-upgrade`, `backup`, `restore` and `evaluate`.

Backup and restore are written in Python (JSON for each table), not with `mysqldump`, so they work on Windows without extra steps.

### `faceid/evaluation.py`: accuracy (§7)

- **LFW pairs**: through `DlibEngine`.
- **Classroom clip**: through `VideoFileSource` → `PresenceTracker`, so it measures the exact code that runs in class.

### `faceid/config.py`: settings

A single dataclass of every setting in F4.5, loaded from `instance/config.toml`. The `instance/` folder is untracked and also holds the generated secret key.

## Tests

| Kind | What | Where it runs |
|---|---|---|
| Unit | `attendance`, `presence`, `enrolment`, `reports.render` through their interfaces | anywhere, instant |
| Integration | `store`, web views (Flask test client) against real MySQL | Linux, podman MySQL |
| Adapter | `DlibEngine` on public-domain sample faces, `VideoFileSource` on a tiny clip | Linux |
| Manual | `docs/windows-checklist.md` | demo laptop, each release |
