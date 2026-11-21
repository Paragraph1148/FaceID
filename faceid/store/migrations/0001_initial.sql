-- SPEC §4: the synopsis's seven tables with the changes listed in its change table (ADRs 0002, 0003, 0005, 0006).

CREATE TABLE admin (
    admin_id      INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email         VARCHAR(100) NOT NULL UNIQUE,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE student (
    student_id           INT AUTO_INCREMENT PRIMARY KEY,
    enrollment_no        VARCHAR(20)  NOT NULL UNIQUE,
    name                 VARCHAR(100) NOT NULL,
    email                VARCHAR(100) UNIQUE,
    mobile               VARCHAR(15)  NULL,
    course               VARCHAR(50)  NOT NULL,
    semester             INT          NOT NULL,
    section              VARCHAR(10)  NULL,
    photo_path           VARCHAR(255) NULL,          -- kept from the synopsis, always empty (ADR 0002)
    is_active            BOOLEAN      DEFAULT TRUE,
    password_hash        VARCHAR(255) NOT NULL,      -- ADR 0003
    must_change_password BOOLEAN      NOT NULL DEFAULT TRUE
);

-- No image_path: face images are never stored (ADR 0002).
CREATE TABLE face_encoding (
    encoding_id     INT AUTO_INCREMENT PRIMARY KEY,
    student_id      INT  NOT NULL,
    encoding_vector BLOB NOT NULL,                   -- 128 little-endian float64 values
    captured_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES student (student_id)
);

CREATE TABLE faculty (
    faculty_id           INT AUTO_INCREMENT PRIMARY KEY,
    name                 VARCHAR(100) NOT NULL,
    email                VARCHAR(100) NOT NULL UNIQUE,
    password_hash        VARCHAR(255) NOT NULL,
    department           VARCHAR(50)  NOT NULL,
    must_change_password BOOLEAN      NOT NULL DEFAULT TRUE,
    is_active            BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE subject (
    subject_id   INT AUTO_INCREMENT PRIMARY KEY,
    subject_code VARCHAR(20)  NOT NULL UNIQUE,
    subject_name VARCHAR(100) NOT NULL,
    semester     INT          NOT NULL,
    faculty_id   INT          NOT NULL,
    course       VARCHAR(50)  NOT NULL,              -- ADR 0006
    is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
    FOREIGN KEY (faculty_id) REFERENCES faculty (faculty_id)
);

CREATE TABLE class_session (
    session_id   INT AUTO_INCREMENT PRIMARY KEY,
    subject_id   INT  NOT NULL,
    faculty_id   INT  NOT NULL,
    session_date DATE NOT NULL,
    start_time   TIME NOT NULL,
    end_time     TIME NOT NULL,
    room_no      VARCHAR(20) NULL,
    status       ENUM('open', 'closed', 'cancelled') DEFAULT 'open',
    FOREIGN KEY (subject_id) REFERENCES subject (subject_id),
    FOREIGN KEY (faculty_id) REFERENCES faculty (faculty_id)
);

CREATE TABLE attendance (
    attendance_id INT AUTO_INCREMENT PRIMARY KEY,
    session_id    INT NOT NULL,
    student_id    INT NOT NULL,
    status        ENUM('present', 'absent', 'late') NOT NULL DEFAULT 'absent',
    marked_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    confidence    FLOAT NULL,
    method        ENUM('face', 'manual') DEFAULT 'face',
    minutes_late  INT NULL,                          -- ADR 0005
    UNIQUE (session_id, student_id),
    FOREIGN KEY (session_id) REFERENCES class_session (session_id),
    FOREIGN KEY (student_id) REFERENCES student (student_id)
);
