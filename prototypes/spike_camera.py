"""PROTOTYPE - throwaway. Answers three questions for FaceID before v0.1.0:

1. Processed FPS of HOG detect + 128-d encode + landmarks at downscale 0.5 vs 0.25 (SPEC N1 needs >= 5).
2. Eye Aspect Ratio values for open vs closed eyes on this webcam (calibrates the 0.22 blink threshold).
3. Does MJPEG streaming from Flask stay smooth with separate capture and recognition threads?

Run:  .venv/bin/python prototypes/spike_camera.py   then open http://127.0.0.1:5050
Switch scale live: http://127.0.0.1:5050/scale/0.25   or /scale/0.5
"""

import sys
import threading
import time
import warnings

warnings.filterwarnings("ignore", category=UserWarning)

import cv2
import face_recognition
from flask import Flask, Response
from scipy.spatial import distance

BACKEND = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_V4L2

state = {
    "frame": None,        # latest raw BGR frame from the camera
    "overlay": [],        # [(top, right, bottom, left, ear)] in full-frame coords
    "scale": 0.5,
    "capture_fps": 0.0,
    "process_fps": 0.0,
    "ear_min": 1.0,       # lowest averaged EAR seen in the last ~2 s
    "ear_max": 0.0,
}
lock = threading.Lock()


def ear(eye):
    # Soukupova & Cech 2016, Eq. 1
    return (distance.euclidean(eye[1], eye[5]) + distance.euclidean(eye[2], eye[4])) / (
        2.0 * distance.euclidean(eye[0], eye[3])
    )


def capture_loop():
    cam = cv2.VideoCapture(0, BACKEND)
    cam.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))  # YUYV caps 720p at ~10 fps
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    count, t0 = 0, time.time()
    while True:
        ok, frame = cam.read()
        if not ok:
            time.sleep(0.01)
            continue
        with lock:
            state["frame"] = frame
        count += 1
        if time.time() - t0 >= 1:
            state["capture_fps"] = count / (time.time() - t0)
            count, t0 = 0, time.time()


def recognition_loop():
    count, t0 = 0, time.time()
    window = []  # (timestamp, ear)
    while True:
        with lock:
            frame = state["frame"]
            scale = state["scale"]
        if frame is None:
            time.sleep(0.01)
            continue
        small = cv2.resize(frame, (0, 0), fx=scale, fy=scale)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        boxes = face_recognition.face_locations(rgb, model="hog")
        face_recognition.face_encodings(rgb, boxes)  # timed, result unused here
        landmarks = face_recognition.face_landmarks(rgb, boxes)
        overlay = []
        for (top, right, bottom, left), marks in zip(boxes, landmarks):
            e = (ear(marks["left_eye"]) + ear(marks["right_eye"])) / 2
            window.append((time.time(), e))
            overlay.append((int(top / scale), int(right / scale), int(bottom / scale), int(left / scale), e))
        window = [(t, e) for t, e in window if time.time() - t < 2]
        with lock:
            state["overlay"] = overlay
            state["ear_min"] = min((e for _, e in window), default=1.0)
            state["ear_max"] = max((e for _, e in window), default=0.0)
        count += 1
        if time.time() - t0 >= 1:
            state["process_fps"] = count / (time.time() - t0)
            print(
                f"scale={scale} process_fps={state['process_fps']:.1f} capture_fps={state['capture_fps']:.1f} "
                f"faces={len(overlay)} ear_min={state['ear_min']:.3f} ear_max={state['ear_max']:.3f}",
                flush=True,
            )
            count, t0 = 0, time.time()


def mjpeg():
    while True:
        with lock:
            frame = None if state["frame"] is None else state["frame"].copy()
            overlay = list(state["overlay"])
        if frame is None:
            time.sleep(0.05)
            continue
        for top, right, bottom, left, e in overlay:
            colour = (0, 0, 255) if e < 0.22 else (0, 200, 0)
            cv2.rectangle(frame, (left, top), (right, bottom), colour, 2)
            cv2.putText(frame, f"EAR {e:.3f}", (left, top - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, colour, 2)
        text = (
            f"scale {state['scale']}  process {state['process_fps']:.1f} fps  capture {state['capture_fps']:.1f} fps  "
            f"EAR 2s min {state['ear_min']:.3f} max {state['ear_max']:.3f}"
        )
        cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n"
        time.sleep(1 / 25)


app = Flask(__name__)


@app.route("/")
def index():
    return '<h3>PROTOTYPE spike</h3><img src="/stream" style="max-width:100%">'


@app.route("/stream")
def stream():
    return Response(mjpeg(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/scale/<float:value>")
def set_scale(value):
    with lock:
        state["scale"] = value
    return f"scale set to {value}. <a href='/'>back</a>"


if __name__ == "__main__":
    threading.Thread(target=capture_loop, daemon=True).start()
    threading.Thread(target=recognition_loop, daemon=True).start()
    app.run(host="127.0.0.1", port=5050, threaded=True)
