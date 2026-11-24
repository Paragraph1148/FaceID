# FaceID

A system that records class attendance by recognising students' faces in a live camera feed. It's used by a college's administrator, faculty and students.

## People

**Admin**:
The person who maintains Students, Faculty and Subjects and performs Face Enrolment.
_Avoid_: Administrator, superuser

**Faculty**:
A teacher who conducts Class Sessions for the Subjects assigned to them.
_Avoid_: Teacher, lecturer, professor

**Student**:
A person enrolled in the college whose attendance is recorded. Identified to people by their Enrolment Number.
_Avoid_: User, learner

**Enrolment Number**:
The university-issued identifier of a Student, e.g. `SSPU20260001`. Stored as `enrollment_no`, the synopsis's column name.
_Avoid_: Roll number, student ID, enrollment ID (in prose)

**Registration**:
Entering or editing the details of a Student, Faculty member or Subject. It never involves faces.
_Avoid_: Sign-up, onboarding

## Teaching

**Programme**:
The degree a Student is studying for, e.g. MCA. Stored as `course` in the database.
_Avoid_: Course (in prose, because it is confusable with Subject), degree, branch

**Subject**:
A unit of study taught to one Programme in one semester, assigned to one Faculty and identified by its Subject Code.
_Avoid_: Course, paper, class

**Class Session**:
One period in which a Faculty teaches a Subject on a given date between a start and end time, and during which attendance is taken.
_Avoid_: Lecture, period, class, session (alone, which clashes with login sessions)

**Expected Students**:
The active Students of a Class Session's Programme and semester; the only Students who get an Attendance Record for it.

**Session Status**:
The state of a Class Session: _open_ (attendance is being taken), _closed_ (attendance is final), or _cancelled_ (the class did not happen).

## Attendance

**Attendance Record**:
The single entry stating one Student's Attendance Status for one Class Session.
_Avoid_: Attendance entry, mark

**Attendance Status**:
_Present_, _late_ or _absent_.

**Late**:
The status of a Student first recognised more than the Late Threshold after the Class Session's start time.

**Minutes Late**:
How many minutes after the Class Session's start time a Late Student was first recognised.

**Late Threshold**:
The number of minutes after a Class Session's start time beyond which recognition counts as Late.

**Marking Method**:
How an Attendance Record got its status: _face_ (by recognition) or _manual_ (by Manual Override).

**Manual Override**:
A Faculty setting an Attendance Record's status by hand.
_Avoid_: Correction, edit

**Attendance Credit**:
How much of one Class Session a Student is counted as having attended: 1 if Present, 0 if Absent, and if Late the fraction of the session remaining after they arrived.

**Attendance Percentage**:
A Student's total Attendance Credit in a Subject as a share of the Subject's held Class Sessions. A held Class Session is a closed one the Student was Expected at: open ones are still in progress and cancelled ones did not happen.

**Defaulter**:
A Student whose Attendance Percentage in a Subject is below the Defaulter Threshold.

**Defaulter Threshold**:
The minimum Attendance Percentage a Student must keep in a Subject, by default 75%.

## Recognition

**Face Enrolment**:
Recording a Student's face as a set of Face Encodings so they can be recognised later.
_Avoid_: Registration, face training, face upload

**Capture**:
One camera image taken during Face Enrolment, discarded as soon as its Face Encoding is made.
_Avoid_: Sample, photo

**Face Encoding**:
A 128-number description of one face, such that faces of the same person lie close together.
_Avoid_: Hash, embedding (in user-facing text), template, signature

**Face Distance**:
The Euclidean distance between two Face Encodings; smaller means more alike.

**Tolerance**:
The largest Face Distance at which two Face Encodings are treated as the same Student.
_Avoid_: Threshold (alone), confidence

**Match Confidence**:
A score derived from the Face Distance of the match that marked a Student present, stored on the Attendance Record.

**Confirmation Frames**:
The number of consecutive frames in which a face must match the same Student before that Student is marked.

**Liveness Check**:
Evidence that a recognised face belongs to a live person in front of the camera, not a photo or screen. Met by a Blink.
_Avoid_: Anti-spoofing (reserved for the optional Spoof Check)

**Blink**:
An eye closure detected from the Eye Aspect Ratio falling below its threshold and recovering.

**Spoof Check**:
An optional extra test that judges a single face image as real or fake, applied on top of the Liveness Check.
