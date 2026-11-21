---
status: accepted
---

# Subjects belong to a Programme

The synopsis's `subject` table has a semester but no Programme, so it can't say which Students are expected in a Class Session when two Programmes share a semester number. For example, closing an MCA semester-1 session would mark every BCA semester-1 Student absent. We add `subject.course` (the Programme, matching `student.course`), and Expected Students are the active Students whose Programme and semester match the Subject's. `student.section` is kept but not used for matching, because the synopsis's `class_session` has no section.
