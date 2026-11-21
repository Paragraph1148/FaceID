---
status: accepted
---

# No face images are stored

The synopsis's `face_encoding.image_path` column (NOT NULL) is dropped. Each Capture is turned into a Face Encoding in memory and then discarded, so the database holds only 128-number encodings, from which a face image can't be rebuilt. The `student.photo_path` column is kept, but stays empty.

This is a deliberate deviation for student privacy: a stolen database or laptop leaks no photographs. The cost is that changing the encoding model later means every Student must go through Face Enrolment again, because there are no stored images to re-encode.
