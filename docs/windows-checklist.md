# Windows checklist

Run this on the demo laptop (Windows 11) for every release. It takes about 20 minutes the first time and 5 minutes after that. Write the results in the table at the end and send them back.

## One-time installs (first release only)

1. **Python 3.10.11**: https://www.python.org/downloads/release/python-31011/ → "Windows installer (64-bit)".
   In the installer, tick **"Add python.exe to PATH"** and keep **"py launcher"** ticked.
2. **MySQL 8.0.46**: https://dev.mysql.com/downloads/installer/ → choose version 8.0.46 → the larger "mysql-installer-community" file.
   - Setup type: **Server only**.
   - Choose a root password and write it down. Setup asks for it.
   - Keep "Configure MySQL Server as a Windows Service" ticked, with the service name **MySQL80**.

## Each release

1. On https://github.com/Paragraph1148/FaceID/releases, download the release's **Source code (zip)** and unzip it to `C:\FaceID-<version>`.
   - Upgrading: copy the `instance` folder from the previous version's folder into the new one first. It holds the settings.
2. Double-click **`setup.bat`**.
   - Windows may warn "Windows protected your PC" → **More info → Run anyway**.
   - It installs packages, which takes a few minutes the first time, then asks for the MySQL root password.
   - First release only: answer `y` to create the Admin account.
   - It must end with green text: **"Setup finished"**.
3. Double-click **`run.bat`**. A browser opens at http://127.0.0.1:5000.
   - If Windows Firewall asks, tick **Private networks** and click **Allow**. That lets phones on the same Wi-Fi reach it.
4. Log in as the Admin.

## Checks for v0.1.0

| # | Do this | Expected |
|---|---|---|
| 1 | Open **Camera diagnostics** in the top menu | The live camera picture appears within 10 seconds |
| 2 | Sit about 50 cm from the laptop | A green box is drawn on your face, with yellow dots on both eyes |
| 3 | Read the black bar at the top of the picture | It shows `DirectShow`, a size such as `1280x720`, and "frames/s processed" |
| 4 | Lean back to about 1.5 m, then to as far as the box still appears | Box stays at 1.5 m |
| 5 | Add a Faculty member, a Subject and a Student | Each appears in its list |
| 6 | In a private browser window, log in as that Student with the Enrolment Number as the password | Asked to choose a new password, then the Student dashboard |
| 7 | On a phone on the same Wi-Fi, open `http://<laptop IP>:5000`. Find the IP by running `ipconfig` and reading "IPv4 Address" | The login page appears |
| 8 | Students → **Enrol face** for a Student. Sit in front of the camera, follow each instruction and press **Capture** five times, then **Save enrolment** | Each capture says "Captured"; the Student list shows **Enrolled (5)** |
| 9 | Start enrolling a *different* Student, but sit in front of the camera yourself (already enrolled) and press **Capture** | Refused: "This face matches …, who is already enrolled" |
| 10 | On the enrolment page, note the **sharp** number on your face's box, sitting still and then moving | Write both numbers in the results table |
| 11 | Close the `run.bat` window | FaceID stops |

## Results to send back

| Item | Value |
|---|---|
| FaceID version | |
| Laptop model, CPU, RAM | |
| Webcam size shown in the black bar (check 3) | |
| frames/s processed with one face (check 3) | |
| Furthest distance the box still appeared (check 4) | |
| Sharpness sitting still / moving (check 10) | |
| Checks that failed (number + screenshot) | |

## If something fails

- **"Python 3.10 not found"**: install Python 3.10.11 as above, then run `setup.bat` again.
- **"Could not reach MySQL"**: open *Services*, find **MySQL80**, and make sure it is *Running*. Then run `setup.bat` again and retype the password.
- **Error mentioning a DLL during "Installing packages" or "dlib does not import"**: install the Microsoft Visual C++ Redistributable (x64) from https://aka.ms/vs/17/release/vc_redist.x64.exe, then run `setup.bat` again.
- **The camera picture says "could not be opened"**: close other apps using the camera (Zoom, Teams, the Camera app) and reload the page.
- **Anything else**: screenshot the whole window and send it.
