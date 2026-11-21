# FaceID

An AI-based face-recognition attendance system. A Faculty member opens a class, the laptop webcam recognises Students, a blink check confirms they are live, and attendance is recorded and exported as Excel, PDF or CSV reports.

Built with Python 3.10, Flask, MySQL 8.0, OpenCV, dlib and face_recognition.

> Status: in development, working towards v1.0.0. See [`CHANGELOG.md`](CHANGELOG.md).

## Documentation

- [Specification](docs/SPEC.md): what the system does, and the milestones
- [Design](docs/DESIGN.md): how the code is organised
- [Glossary](GLOSSARY.md): the domain words
- [Decisions](docs/adr/): why things are the way they are

## Privacy

No face images are stored. Each enrolment photo is turned into a 128-number Face Encoding and then discarded.


## Running

**Windows (the demo laptop):** follow [`docs/windows-checklist.md`](docs/windows-checklist.md). In short, `setup.bat` once, then `run.bat`.

**Linux (development):**

```bash
uv python install 3.10 && uv venv --python 3.10 .venv
uv pip install --python .venv -r requirements-dev.txt
uv pip install --python .venv --no-deps face_recognition==1.3.0
podman run -d --name faceid-mysql -e MYSQL_ROOT_PASSWORD=<password> -p 127.0.0.1:3306:3306 \
  -v faceid-mysql:/var/lib/mysql:Z docker.io/library/mysql:8.0.46
# create instance/config.py with the DB_* settings (see setup.ps1); the secret key is generated on first run
.venv/bin/flask --app faceid db-upgrade
.venv/bin/flask --app faceid create-admin
.venv/bin/flask --app faceid run
.venv/bin/python -m pytest
```

## Licence

[MIT](LICENSE). Bootstrap is MIT-licensed by its authors (`faceid/static/vendor/bootstrap/LICENSE`).
