---
status: accepted
---

# Students get a password column

The synopsis promises a Student login but its `student` table has no credential. We add `student.password_hash` (bcrypt, like `admin` and `faculty`). The Admin sets the initial password to the Student's Enrolment Number, and the Student must change it at first login. Logging in by Enrolment Number alone was rejected because Enrolment Numbers are printed on ID cards and lists, so anyone could read anyone else's attendance.
