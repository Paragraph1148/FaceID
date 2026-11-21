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

## Licence

[MIT](LICENSE)
