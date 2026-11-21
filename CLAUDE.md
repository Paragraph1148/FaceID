# FaceID

A face-recognition attendance web app for an MCA minor project. Every feature traces to the approved synopsis, which is binding on features, algorithms and stack ([ADR 0001](docs/adr/0001-synopsis-is-binding.md)).

## Read before working

- **Spec**: [`docs/SPEC.md`](docs/SPEC.md). Requirement IDs (F3.2, N1) are the vocabulary for branches, tests and PRs.
- **Module layout and seams**: [`docs/DESIGN.md`](docs/DESIGN.md). Rules live in the pure modules (`attendance`, `presence`, `enrolment`). Views and adapters stay thin.
- **Domain words**: [`GLOSSARY.md`](GLOSSARY.md). Use its canonical terms in code, UI text and docs.
- **Why something is the way it is**: `docs/adr/`. Any departure from the synopsis gets a new ADR.
- **Install quirks and version pins**: [`docs/research/2026-11-21-stack-facts.md`](docs/research/2026-11-21-stack-facts.md).

## Gotchas

- Install `face_recognition` with `pip install --no-deps face_recognition==1.3.0`. dlib comes from `dlib-bin`, which pip does not count as `dlib`.
- Keep `setuptools<82`. `face_recognition_models` needs `pkg_resources`, and without it `import face_recognition` quits with a misleading message.
- On Fedora, MySQL 8.0.46 runs in podman (`docker.io/library/mysql:8.0.46`), never the distro's 8.4 or MariaDB.
- On Windows, open the webcam with `cv2.CAP_DSHOW`.

## Privacy

Face images exist only in memory, between Capture and Face Encoding. The repo holds code and public-domain test fixtures only. Synopsis, names, enrolment data, databases, recordings and backups stay outside git: `docs/private/` and `instance/` are ignored for this.

## Code style

The author defends this code alone in a viva. Write plain, explicit Python with type hints on module functions (Flask views and Jinja macros are exempt), small functions and one-line comments that explain *why*. Prefer the standard library to new dependencies, because every dependency must be justified against the synopsis.

## Releases

Semver, starting at 0.1.0. Plain git only: there are no GitHub PRs and the `gh` CLI is not installed. Each milestone in SPEC §8 goes through:
1. A `feat/<milestone>` branch, pushed.
2. TDD.
3. `code-review` against `main`, with fixes.
4. A version bump in `faceid/__init__.py` and a `CHANGELOG.md` entry.
5. `git merge --no-ff` into `main`. The merge commit message is the PR description, written with the `pr` skill and passed with `-F <file>` (`git merge` can't read the message from stdin).
6. An annotated `vX.Y.Z` tag on the merge commit. Check `git log -1` before tagging.
7. `git push origin main vX.Y.Z`. Push without asking.

Commit with the repo-local identity (the noreply email is already set in `.git/config`). Use Conventional Commit messages.
