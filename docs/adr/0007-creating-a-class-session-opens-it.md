---
status: accepted
---

# Creating a Class Session opens it

The synopsis's `class_session.status` has only `open`, `closed` and `cancelled`, so a session can't be created ahead of time and opened later without a fourth status. A Faculty member therefore creates a Class Session when the class begins: creating it opens it, creates the absent Attendance Records for the Expected Students and starts recognition. Its date is always today. The start time can be earlier than now, for a class that started before the camera was set up, and lateness is measured from that start time.

## Considered Options

- **Add a `scheduled` status**: allows a timetable, which the synopsis doesn't ask for, and changes a synopsis column.
- **Treat `open` sessions with no Attendance Records as scheduled**: two meanings for one status, and "one open session per server" (F5.2) would block scheduling.

## Consequences

- There is no timetable. Each Class Session is created on the day.
- If the server restarts while a session is open, the session stays open in the database and recognition resumes when the Faculty opens its page, on the same day. A session left open from an earlier day is never resumed, because everyone would be marked hours late; the page asks the Faculty to close it.
