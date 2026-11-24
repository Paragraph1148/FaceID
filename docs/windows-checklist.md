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

## Checks

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
| 11 | On the enrolment page: press **Capture** with nobody in view; then with two people in view; then from 3 m away; then while moving your head quickly | Refused each time, with the reason: no face / 2 faces / too small / blurred |
| 12 | Sit at 50 cm and watch the box | Green when you're close and still; amber when too far or moving |
| 13 | Enrol an already-enrolled Student again (**Re-enrol face**) and save | The Student list still shows **Enrolled (5)**, not 10 |
| 14 | As the Admin, make sure the Subject from check 5 is in the same Programme and semester as the enrolled Student. Log in as its Faculty member (private window) and press **Start a Class Session** with the current time | The session page shows the live camera and "0 / N Students marked" |
| 15 | The enrolled Student sits at 50 cm and looks at the camera without blinking for 5 seconds | Amber box: "*name*: blink to confirm". Not marked |
| 16 | The Student blinks once | The box turns green within about a second; the count goes up and the name appears in the list. Without reloading the page, the Attendance Records row shows **Present**, method **face** |
| 17 | Hold a phone photo of the enrolled Student up to the camera | Amber box at most; never marked (unless already marked) |
| 18 | Start another session with a start time 25 minutes ago (close the first one), then let the Student blink | Marked **Late (25 min)** |
| 19 | In **Manual Override**, set another Student to Late with 15 minutes, and save | The row shows **Late (15 min)**, method **manual** |
| 20 | Read "Recognition: … frames/s" with one face, and with as many faces as you can gather | Write both numbers in the results table |
| 21 | Press **Close Class Session** | Status **Closed**; the camera light goes off within about 15 seconds |
| 22 | As the Faculty member, open **Reports**, choose **Subject-wise report** for the Subject, and press **View** | One row per Student with Held, Present, Late, Absent and Attendance Percentage. Only closed Class Sessions count |
| 23 | Press **XLSX**, **PDF** and **CSV** in turn, and open each file | Excel opens the xlsx and the CSV, a PDF viewer opens the PDF, and all three have the same rows as the page |
| 24 | Open **Defaulter list** for the Subject with threshold 75, then with 101 | The Students below 75%; then "Enter a Defaulter Threshold from 1 to 100." |
| 25 | Log in as the enrolled Student (private window) | **My attendance** shows their own Subjects and session history, nobody else's |
| 26 | Close the `run.bat` window. Double-click **`backup.bat`** and type `D:\faceid-backup.json` (or any folder outside FaceID) | "Saved … to D:\faceid-backup.json" |
| 27 | Double-click **`restore.bat`**, type the same path, and answer `y`. Start `run.bat` and log in as the Student | "Restored …"; the Student's attendance is unchanged. Keep the backup file private: it holds names and Face Encodings |
| 28 | Close the `run.bat` window | FaceID stops |

## Results to send back

| Item | Value |
|---|---|
| FaceID version | |
| Laptop model, CPU, RAM | |
| Webcam size shown in the black bar (check 3) | |
| frames/s processed with one face (check 3) | |
| Furthest distance the box still appeared (check 4) | |
| Sharpness sitting still / moving (check 10) | |
| Recognition frames/s with one face / most faces, and how many faces (check 20) | |
| Checks that failed (number + screenshot) | |

## If something fails

- **"Python 3.10 not found"**: install Python 3.10.11 as above, then run `setup.bat` again.
- **"Could not reach MySQL"**: open *Services*, find **MySQL80**, and make sure it is *Running*. Then run `setup.bat` again and retype the password.
- **Error mentioning a DLL during "Installing packages" or "dlib does not import"**: install the Microsoft Visual C++ Redistributable (x64) from https://aka.ms/vs/17/release/vc_redist.x64.exe, then run `setup.bat` again.
- **The camera picture says "could not be opened"**: close other apps using the camera (Zoom, Teams, the Camera app) and reload the page.
- **Anything else**: screenshot the whole window and send it.
