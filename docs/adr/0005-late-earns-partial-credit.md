---
status: accepted
---

# Late arrival earns partial attendance credit

Lateness is measured, not just flagged, and it costs attendance in proportion to how late the Student was. Each Attendance Record stores `minutes_late` (an added column), and a Late Student's Attendance Credit for that Class Session is the fraction of the session remaining after they arrived. For example, someone arriving 15 minutes into a 60-minute session earns 0.75. Present earns 1 and Absent earns 0. Arriving within the Late Threshold counts as Present with full credit. Attendance Percentage is the sum of credits divided by the number of held Class Sessions.

## Considered Options

- **Late counts as fully attended**: makes lateness free, so the status carries no weight.
- **Late counts a fixed fraction (e.g. 0.5)**: simpler, but it treats arriving 11 minutes late the same as arriving 50 minutes late.

## Consequences

- The credit is derived from `minutes_late` and the session's start and end times, never stored, so changing the rule doesn't need a data migration.
- If the camera misses a Student who was actually there on time, the Faculty uses Manual Override to set them Present, which restores full credit.
