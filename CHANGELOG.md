# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/Paragraph1148/FaceID/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Paragraph1148/FaceID/releases/tag/v0.1.0
