---
status: accepted
---

# The camera is read by the server, on the Faculty's laptop

The Flask server runs on the Faculty's laptop and reads that laptop's webcam directly with OpenCV, then streams annotated frames to the browser. Other devices on the local network (e.g. Students' phones) use the same server for dashboards and reports, but only the server's own camera can take attendance.

We chose this over capturing in the browser and uploading frames because the synopsis describes server-side OpenCV capture, it avoids browser camera-permission rules that require HTTPS on non-localhost origins, and recognition runs on the frames at full resolution with no network latency. The consequence is that a Class Session can only run on the machine that hosts the server, and only one Class Session can take attendance at a time, because there's one camera.
