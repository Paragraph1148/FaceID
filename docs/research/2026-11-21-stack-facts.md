# Stack facts for FaceID (researched 2026-11-21)

Scope: verified facts for the synopsis-mandated stack (Python 3.10, Flask 3.x, Flask-Login, MySQL 8.0, mysql-connector-python, OpenCV, dlib, face_recognition, NumPy, SciPy, Pandas, openpyxl, ReportLab, imutils, bcrypt). Sources are primary: PyPI JSON API, upstream GitHub source, dev.mysql.com, the papers. Anything not confirmed is marked **UNVERIFIED**.

"Empirically verified" means it was run on the Fedora 45 dev machine in a throwaway CPython 3.10.21 venv on 2026-11-21. Windows was **not** tested.

---

## Decisions this implies

### Pinned versions (each is the newest release that supports Python 3.10 and has cp310, abi3 or pure wheels for win_amd64 and manylinux x86_64)

```text
# requirements.txt  (Python 3.10)
flask==3.1.3
flask-login==0.6.3
mysql-connector-python==26.10.0
opencv-python==4.14.0.94        # newest 4.x; 5.x exists (5.1.0.95), see Q6
numpy==2.2.6                    # last numpy supporting 3.10
scipy==1.15.3                   # last scipy supporting 3.10
pandas==2.3.3                   # last pandas supporting 3.10
openpyxl==3.1.5
reportlab==5.1.0
imutils==0.5.4                  # sdist only (pure Python)
bcrypt==5.0.0
pillow==12.3.0                  # last Pillow supporting 3.10
click==8.5.1
dlib-bin==20.0.1.post1          # prebuilt dlib; provides `import dlib`
face_recognition_models==0.3.0  # sdist only; needs pkg_resources at runtime
setuptools==81.0.0              # MUST stay <82: 82 removed pkg_resources
pytest==9.2.0                   # dev/test
# face_recognition==1.3.0 is installed separately with --no-deps (see below)
```

Empirically verified on Linux: all of the above resolved and imported together. `uv pip check` reported only the expected `face-recognition requires dlib>=19.7` mismatch. `face_recognition` detected, encoded (128-d float64) and landmarked a test face with numpy 2.2.6.

### dlib install route (no C++ compiler), the same on Windows 11 and Fedora

```bash
python -m pip install -r requirements.txt
python -m pip install --no-deps face_recognition==1.3.0
```

- `--no-deps` is required. `face_recognition` declares `dlib>=19.7`, and `dlib-bin` installs under a different distribution name. Without `--no-deps`, pip tries to build `dlib` from its sdist, which needs CMake and a compiler. Verified with a dry run, which planned `+ dlib==20.0.1`.
- Keep `setuptools<82` in the venv. Otherwise `import face_recognition` prints "Please install `face_recognition_models`" and calls `quit()`.
- The prebuilt dlib is **CPU-only**. `dlib.DLIB_USE_CUDA` returned `False` for the Linux wheel. Use the HOG detector (`model="hog"`, the default), which the synopsis already specifies.
- Optional GPU fallback (not needed): conda-forge has CUDA builds of dlib 20.0.1 for win-64 py310.

### MySQL route

- **Windows demo laptop:** MySQL Installer 8.0.46 (`mysql-installer-community-8.0.46.0.msi`). It is still on dev.mysql.com/downloads/installer and the CDN serves it (HTTP 200).
- **Fedora 45 dev:** Fedora no longer packages MySQL 8.0 (only `mysql8.4-server` and `mariadb-server`). Run the official container instead: `podman run -d --name faceid-mysql -e MYSQL_ROOT_PASSWORD=... -p 3306:3306 -v faceid-mysql:/var/lib/mysql:Z docker.io/library/mysql:8.0.46`
- Pin `8.0.46` on both machines. It is the final 8.0 release.

---

## Q1. dlib, face_recognition and face_recognition_models installation

### dlib on PyPI
- `dlib` 20.0.1 (2026-03-29) ships **only an sdist** (`dlib-20.0.1.tar.gz`), so installing it needs CMake and a C++ compiler. The last wheels PyPI ever had were for old Windows CPythons (cp27 to cp36, up to 19.5.x). Source: https://pypi.org/pypi/dlib/json
- Upstream dlib tagged v20.1 on 2026-11-14 (https://api.github.com/repos/davisking/dlib/releases). It is **not** on PyPI as `dlib` or `dlib-bin` yet.

### dlib-bin
- Latest version: `dlib-bin` 20.0.1.post1 (uploaded 2026-10-02). It ships `dlib_bin-20.0.1.post1-cp310-cp310-win_amd64.whl` and `...-cp310-cp310-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl`. Licence: Boost Software License. Source: https://pypi.org/pypi/dlib-bin/json
- Who builds it: the author field says Davis King, but the homepage is https://github.com/alesanfra/dlib-wheels. That is a third-party repo (not Davis King's) that builds upstream dlib with cibuildwheel and publishes to PyPI. It is not archived, and it was last pushed 2026-11-15 (https://api.github.com/repos/alesanfra/dlib-wheels).
- Its README lists Windows AMD64, manylinux_2_28 and musllinux x86_64/aarch64, and macOS arm64 (https://github.com/alesanfra/dlib-wheels/blob/master/README.md). It says: "Starting with version 20.0.1 (March 2026), this distribution builds binary wheels for Python 3.10, 3.11, 3.12, 3.13, 3.14, and 3.15."
- `master` already targets `BUILD_COMMIT: "v20.1"` / `DLIB_BIN_VERSION: "20.1"`. It is not published yet. Source: https://github.com/alesanfra/dlib-wheels/blob/master/.github/workflows/build.yaml
- **Does it satisfy face_recognition's `dlib` requirement? No.** It installs the distribution name `dlib-bin` while providing the `dlib` module. pip resolves requirements by distribution name, so `face_recognition`'s `dlib>=19.7` is unmet. Empirically verified: `uv pip install --dry-run face_recognition==1.3.0` planned `+ dlib==20.0.1` (a source build). The workaround is `--no-deps`.
- **CUDA:** the build workflow installs only `cmake` (`CIBW_BEFORE_BUILD: pip install cmake`) and sets no CUDA toolkit or flags. Empirically, the Linux wheel reports `dlib.DLIB_USE_CUDA == False`.
  - The Windows wheel's CUDA state is **UNVERIFIED**, because it was not run on Windows. It is almost certainly CPU-only, since the Windows build has no CUDA toolkit step.
  - The CNN detector (`model="cnn"`) still runs on CPU, just slowly. HOG is the intended detector anyway.
- Upstream issue on CUDA DLL loading on Windows: https://github.com/davisking/dlib/issues/2039 (open).

### conda-forge dlib
- Latest version: 20.0.1. win-64 py310 builds exist in CPU (`cpu_py310hce1b4a1_*`), CUDA 12.9 (`cuda129py310h87f52a6_*`) and CUDA 13.0 (`cuda130py310h2af37dd_*`) variants. linux-64 has the same set. Source: https://api.anaconda.org/package/conda-forge/dlib
- This is the only prebuilt **GPU** route on Windows. Whether pip then treats a conda-installed `dlib` as satisfying `face_recognition`'s requirement is **UNVERIFIED**, and so is whether conda's dlib registers dist-info that pip can see.

### face_recognition
- PyPI latest: **1.3.0** (2020-02-20). It is a universal wheel (`py2.py3-none-any`) with no `requires_python`. Source: https://pypi.org/pypi/face_recognition/1.3.0/json
- `requires_dist`: `face-recognition-models (>=0.3.0)`, `Click (>=6.0)`, `dlib (>=19.7)`, `numpy`, `Pillow`.
- GitHub `master` `setup.py` says version **1.4.0** with the same requirements (https://github.com/ageitgey/face_recognition/blob/master/setup.py). Its HISTORY.rst says 1.4.0 (2020-09-26) dropped Python 2 support. 1.4.0 was **never published to PyPI**.
- README:
  - "Windows not officially supported, but might work".
  - Default tolerance is 0.6.
  - "an accuracy of 99.38% on the Labeled Faces in the Wild benchmark".
  - Source: https://github.com/ageitgey/face_recognition/blob/master/README.md
- `api.py` details (https://github.com/ageitgey/face_recognition/blob/master/face_recognition/api.py):
  - It loads all models at import time, including the CNN detector.
  - `face_encodings(..., model="small")` defaults to the 5-point landmark model.
  - `compare_faces(..., tolerance=0.6)`.
  - `face_locations(..., model="hog")` defaults to HOG.

### face_recognition_models
- PyPI latest: **0.3.0** (2017-09-28). It is **sdist only**, so pip builds it locally. That needs setuptools but no compiler. Source: https://pypi.org/pypi/face_recognition_models/json
- Its `__init__.py` does `from pkg_resources import resource_filename` (https://github.com/ageitgey/face_recognition_models/blob/master/face_recognition_models/__init__.py).
- **setuptools removed `pkg_resources` in v82.0.0.** The changelog says: "``pkg_resources`` has been removed from Setuptools… Projects and environments relying on ``pkg_resources``… should depend on older versions of ``setuptools``." Source: https://github.com/pypa/setuptools/blob/main/NEWS.rst
  - The latest setuptools is 84.2.1. The newest release before 82 is **81.0.0**, and it is the only 81.x.
- **Failure mode:** `face_recognition/api.py` wraps `import face_recognition_models` in `except Exception:`. On failure it prints "Please install `face_recognition_models`…" and calls `quit()`. A missing `pkg_resources` therefore shows up as a misleading "models not installed" message.
  - Open upstream issues: https://github.com/ageitgey/face_recognition/issues/1653 and https://github.com/ageitgey/face_recognition/issues/1645
  - Empirically verified: with setuptools<82, the import works and emits only a `UserWarning` deprecation.

---

## Q2. MySQL 8.0

- **EOL:** the MySQL 8.0 release notes say: "As of April 2026, with version 8.0.46, MySQL 8.0 reaches End of Life (EoL). MySQL 8.0 users are encouraged to upgrade to the latest MySQL 8.4 LTS or MySQL Innovation release." Source: https://dev.mysql.com/doc/relnotes/mysql/8.0/en/index.html
  - **Exact day: UNVERIFIED** from an Oracle primary source. Third-party sources say April 30, 2026, but Oracle's Lifetime Support PDF returned HTTP 403.
- **Latest 8.0.x: 8.0.46**, released 2026-04-21. It is the final release (same source).
- **MySQL Installer for Windows** (https://dev.mysql.com/downloads/installer/): still offered, with versions 8.0.46 and 5.7.44.
  - Files: `mysql-installer-web-community-8.0.46.0.msi` (2.1 MB) and `mysql-installer-community-8.0.46.0.msi` (565.9 MB).
  - The page says: "MySQL 8.0 is the final series with MySQL Installer. As of MySQL 8.1, use a MySQL product's MSI or Zip archive."
  - Both MSI URLs under `https://cdn.mysql.com/Downloads/MySQLInstaller/` returned HTTP 200 on 2026-11-21.
  - `downloads.mysql.com/archives/installer/` returned HTTP 403 to automated clients. **UNVERIFIED** (it probably works in a browser).
- **Fedora 45:** `dnf repoquery` shows `mysql8.4-server` (8.4.11 and 8.4.13) and `mariadb-server` (12.3.2), with **no `community-mysql` or `mysql8.0` package**. So MySQL 8.0 is not available through dnf (checked locally on this machine).
- **Container:** the Docker Hub `library/mysql` tags `8.0`, `8.0.46`, `8.0.46-oraclelinux9` and `8.0-debian` exist. `8.0` was last updated 2026-05-05 and covers amd64 and arm64 (https://hub.docker.com/v2/repositories/library/mysql/tags/8.0).
  - 8.0 is **no longer in the official-images manifest**, which now lists 26.10 (innovation/latest), 9.7 (lts) and 8.4 only (https://github.com/docker-library/official-images/blob/master/library/mysql). The 8.0 image is frozen and will get no more rebuilds.
  - Use `docker.io/library/mysql:8.0.46` with podman.

---

## Q3. Eye Aspect Ratio (EAR)

- **Paper:** T. Soukupová and J. Čech, "Real-Time Eye Blink Detection using Facial Landmarks", 21st Computer Vision Winter Workshop (CVWW), Rimske Toplice, Slovenia, Feb 3–5 2016. PDF: https://vision.fe.uni-lj.si/cvww2016/proceedings/papers/05.pdf
- **Formula (Eq. 1):** `EAR = (‖p2 − p6‖ + ‖p3 − p5‖) / (2 ‖p1 − p4‖)`, "where p1, …, p6 are the 2D landmark locations". p1 and p4 are the eye corners, p2/p3 are on the upper lid and p6/p5 on the lower lid.
  - The paper says EAR "is mostly constant when an eye is open and is getting close to zero while closing an eye".
  - It also says "the EAR of both eyes is averaged".
- **What the paper says about thresholds:**
  - It uses a fixed threshold only as a **baseline**: "EAR thresholding (threshold set to 0.2)", in the Fig. 2 caption.
  - It argues that "It generally does not hold that low value of the EAR means that a person is blinking".
  - Its proposed method is a linear SVM ("EAR SVM") on a 13-dimensional feature: the EAR of ±6 frames around each frame, for 30 fps video.
  - The SVM outperforms plain thresholding.
  - The paper's landmark detectors were Chehra and Intraface, **not dlib**.
- **face_recognition landmark keys:** `face_landmarks(model="large")` (the default) returns `chin`, `left_eyebrow`, `right_eyebrow`, `nose_bridge`, `nose_tip`, `left_eye` = `points[36:42]` (6 points), `right_eye` = `points[42:48]` (6 points), `top_lip` and `bottom_lip`. Source: api.py, linked above.
  - The 6 points are in iBUG-68 order: corner, two upper-lid points, corner, two lower-lid points. So `eye[0..5]` maps to p1..p6 directly.
  - `model="small"` returns only 2 points per eye, which is unusable for EAR.
  - Empirically verified: 6 points per eye.
- **Values used in practice:**
  - face_recognition's own `examples/blink_detection.py` computes EAR as `(A+B)/(2C)` with `scipy.spatial.distance.euclidean`, treats eyes as closed when `ear_left < 0.2 and ear_right < 0.2`, and counts consecutive closed frames (https://github.com/ageitgey/face_recognition/blob/master/examples/blink_detection.py).
  - A. Rosebrock's widely copied dlib tutorial (2017-04-24) uses `EYE_AR_THRESH = 0.3` and `EYE_AR_CONSEC_FRAMES = 3`, and says both "may need to [be tuned]" for your frame rate (https://pyimagesearch.com/2017/04/24/eye-blink-detection-opencv-python-dlib/).
  - **Recommendation (inference, not sourced):** threshold about 0.2–0.25, at least 2–3 consecutive frames below it, then a rise back above it. Calibrate on the demo webcam, because the effective FPS after HOG detection will be well below 30.

---

## Q4. LFW (Labeled Faces in the Wild)

- **Official site:** http://vis-www.cs.umass.edu/lfw/. **It is currently down.** On 2026-11-21 the hostname `vis-www.cs.umass.edu` did not resolve in DNS.
  - The latest Wayback snapshot is from 2025-01-05 (http://web.archive.org/web/20250105180242/http://vis-www.cs.umass.edu/lfw/).
  - A TensorFlow Datasets issue reports the same DNS failure: https://github.com/tensorflow/datasets/issues/11012. Its date is **UNVERIFIED**.
- **Protocol:** G. B. Huang, M. Ramesh, T. Berg, E. Learned-Miller, "Labeled Faces in the Wild: A Database for Studying Face Recognition in Unconstrained Environments", UMass Amherst Tech. Report 07-49, 2007 (https://people.cs.umass.edu/~elm/papers/lfw.pdf).
  - The dataset has 13,233 images of 5,749 people.
  - View 1 is for development (pairsDevTrain/pairsDevTest). View 2 "consists of ten subsets" for performance reporting, using leave-one-out 10-fold cross-validation.
  - Authors should "report the estimated mean accuracy and the standard error of the mean for View 2".
  - `pairs.txt` starts with the header line `10	300`: 10 folds × (300 matched + 300 mismatched) pairs. Verified from the mirror file, 6001 lines.
- **Licence / terms:**
  - The archived homepage has a **DISCLAIMER**: "No matter what the performance of an algorithm on LFW, it should not be used to conclude that an algorithm is suitable for any commercial purpose." It notes poor representation of children, people over 80, women and many ethnicities.
  - No formal licence text was found on the archived homepage. **Licence: UNVERIFIED.**
- **dlib/face_recognition accuracy:**
  - dlib's example says "the dlib model obtains an accuracy of 99.38% on the standard LFW face recognition benchmark", maps faces to "128 dimensional vector space", and treats a Euclidean distance below 0.6 as the same person (http://dlib.net/face_recognition.py.html).
  - The face_recognition README repeats 99.38%.
- **scikit-learn mirror:**
  - `sklearn/datasets/_lfw.py` downloads from figshare, not UMass, with SHA-256 checksums: `lfw.tgz` = https://ndownloader.figshare.com/files/5976018, `pairs.txt` = https://ndownloader.figshare.com/files/5976006 (sha256 `ea42330c…dc1592`), plus pairsDevTrain and pairsDevTest. `fetch_lfw_pairs(subset="10_folds")` uses `pairs.txt`.
  - Source: https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/datasets/_lfw.py. scikit-learn 1.7.2 uses the same URLs.
  - Verified on 2026-11-21: `pairs.txt` downloaded and matched the checksum, and a range GET of `lfw.tgz` returned 206.
  - **Caveats:**
    - Latest scikit-learn 1.9.1 requires Python ≥3.11. The last version for 3.10 is **1.7.2**.
    - `fetch_lfw_pairs` returns cropped, downscaled grey arrays by default, so a face_recognition evaluation should read the raw JPEGs from `lfw.tgz`.
    - figshare is a mirror rather than a guaranteed host. Download it once and keep a copy.

---

## Q5. Flask MJPEG streaming and OpenCV capture

- **Flask docs** cover generator streaming (`Response(generate())`, `stream_with_context`) but **do not document MJPEG** (https://github.com/pallets/flask/blob/3.1.3/docs/patterns/streaming.rst).
  - The canonical MJPEG pattern comes from Miguel Grinberg's reference repo, https://github.com/miguelgrinberg/flask-video-streaming (`app.py`): `Response(gen(camera), mimetype='multipart/x-mixed-replace; boundary=frame')`, yielding `b'--frame\r\n'` then `b'Content-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n'`.
  - Its `base_camera.py` uses a **single class-level background `threading.Thread`** that owns the camera and stores the latest `frame`. A `CameraEvent` wakes every client thread when a new frame arrives, and the thread stops after 10 s with no clients.
  - This is the recommended "one capture thread, shared latest frame" design. Do not open `VideoCapture` once per request.
- **Flask dev server threading:** `Flask.run()` does `options.setdefault("threaded", True)` (https://github.com/pallets/flask/blob/3.1.3/src/flask/app.py, line ~655). Each request, including each long-lived MJPEG stream, gets its own thread by default.
- **OpenCV backends** (https://github.com/opencv/opencv/blob/4.x/modules/videoio/include/opencv2/videoio.hpp): `CAP_DSHOW = 700` (DirectShow) and `CAP_MSMF = 1400` (Microsoft Media Foundation). On Windows the default (`CAP_ANY`) picks MSMF.
- **MSMF slow open:**
  - https://github.com/opencv/opencv/issues/17687 ("Camera is very slow to open when using the MSMF VideoCapture backend", with startups of several minutes).
  - It was fixed by PR https://github.com/opencv/opencv/pull/20327 (merged 2021-06-30), which added the env var `OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS` (default `true`; see `cap_msmf.cpp`, `getConfigurationParameterBool(..., true)`). Set it to `0` to disable hardware transforms.
  - Comments in the issue say it must be set **before** cv2 initialises the backend. Setting it in the shell or at the very top of the entry point, before `import cv2`, is safest, and some users found that `os.environ` after import did not help.
  - A related issue, https://github.com/opencv/opencv/issues/27917 (closed 2025-10-17), reports slow first frames on MSMF when resolution is set, with DSHOW unaffected.
  - **Practical choice:** on Windows, open with `cv2.VideoCapture(0, cv2.CAP_DSHOW)`. Fall back to MSMF with `OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0` if DSHOW misbehaves. On Fedora, use `CAP_V4L2`.

---

## Q6. Latest Python 3.10-compatible versions (PyPI JSON API, 2026-11-21)

Method: for each package, newest non-prerelease, non-yanked release whose `requires_python` admits 3.10, with a cp310, abi3 (≤cp310) or pure wheel for both win_amd64 and manylinux x86_64. Source: `https://pypi.org/pypi/<pkg>/json`.

| Package | Latest overall (requires_python) | Pin for 3.10 | Wheel evidence / notes |
|---|---|---|---|
| flask | 3.1.3 (>=3.9) | **3.1.3** | pure |
| flask-login | 0.6.3 (>=3.7) | **0.6.3** | pure; last release 2023-10-30 |
| mysql-connector-python | 26.10.0 (>=3.10) | **26.10.0** | cp310 win_amd64 + manylinux_2_28 + pure wheel. Connector version numbers are now independent of the server's. Compatibility with an 8.0 server is **UNVERIFIED** from release notes, but the import works. |
| opencv-python | 5.1.0.95 (2026-11-17) | **4.14.0.94** (newest 4.x) | cp37-abi3 win_amd64/manylinux. 4.14 and 5.x require `numpy>=2` on py≥3.9. 5.x also supports 3.10. Choosing 4.x over the 4-day-old 5.1 is a stability choice, not a compatibility one. |
| opencv-python-headless | 5.1.0.95 | 4.14.0.94 if used | same wheels. face_recognition needs only numpy arrays, so headless works for a server with no `cv2.imshow`. Install **only one** of the two packages. |
| numpy | 2.5.5 (>=3.12) | **2.2.6** | numpy 2.3+ dropped 3.10 |
| scipy | 1.18.1 (>=3.12) | **1.15.3** | scipy 1.16+ dropped 3.10; 1.15.3 needs `numpy<2.5,>=1.23.5` |
| pandas | 3.1.1 (>=3.11) | **2.3.3** | pandas 3.x dropped 3.10 |
| openpyxl | 3.1.5 (>=3.8) | **3.1.5** | pure |
| reportlab | 5.1.0 (<4,>=3.9) | **5.1.0** | pure; needs pillow>=9, charset-normalizer |
| imutils | 0.5.4 (none) | **0.5.4** | **sdist only**, pure Python, builds without a compiler; last release 2021 |
| bcrypt | 5.0.0 (>=3.8) | **5.0.0** | cp38/cp39-abi3 win_amd64 + manylinux |
| pytest | 9.2.0 (>=3.10) | **9.2.0** | pure |
| Pillow | 13.0.0 (>=3.11) | **12.3.0** | Pillow 13 dropped 3.10 |
| click | 8.5.1 (>=3.10) | **8.5.1** | pure |
| setuptools | 84.2.1 (>=3.10) | **81.0.0** | pinned below 82 for `pkg_resources` (Q1) |
| scikit-learn (optional, LFW) | 1.9.1 (>=3.11) | 1.7.2 | only if `fetch_lfw_pairs` is wanted |
| face_recognition | 1.3.0 | 1.3.0 | universal wheel; install with `--no-deps` |
| face_recognition_models | 0.3.0 | 0.3.0 | sdist only |
| dlib-bin | 20.0.1.post1 | 20.0.1.post1 | cp310 win_amd64 + manylinux_2_28 |

**numpy 2 and dlib:**
- dlib v20.0.1 bundles **pybind11 2.12.0** (`dlib/external/pybind11/include/pybind11/detail/common.h`). pybind11 2.12.0 is NumPy-2-aware: its `numpy.h` picks `numpy._core` vs `numpy.core` by NumPy major version.
- dlib 19.24.4 bundled pybind11 2.10.0 (not NumPy-2-aware). 19.24.6 bundled 2.12.0. Source: https://github.com/davisking/dlib/tree/v20.0.1/dlib/external/pybind11
- **Empirically verified:** `dlib-bin` 20.0.1.post1 with numpy 2.2.6 on CPython 3.10.21 (Linux) ran `face_locations`, 128-d `face_encodings` and `face_landmarks` correctly. It also accepted a non-contiguous `bgr[:, :, ::-1]` view.
- Windows behaviour with numpy 2 is **UNVERIFIED**, because it was not run on Windows.

---

## Open items / UNVERIFIED
1. Whether the `dlib-bin` win_amd64 wheel imports cleanly on the demo laptop (VC++ runtime needs) and whether it is CPU-only. Run `python -c "import dlib; print(dlib.DLIB_USE_CUDA)"` on Windows.
2. Exact MySQL 8.0 EOL day (Oracle says "April 2026"; third parties say 2026-04-30).
3. LFW licence text. The site is offline, and only the disclaimer was recovered from the archive.
4. Whether `mysql-connector-python` 26.10 officially supports MySQL Server 8.0 (check https://dev.mysql.com/doc/connector-python/en/connector-python-versions.html).
5. Whether a conda-installed dlib satisfies pip's `dlib` requirement.
