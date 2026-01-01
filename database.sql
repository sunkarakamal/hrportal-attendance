create database IF NOT Exists gps_face_db;
use gps_face_db;

CREATE TABLE IF NOT Exists users (
    id INT NOT NULL AUTO_INCREMENT,
    username VARCHAR(50) UNIQUE,
    email VARCHAR(100) UNIQUE,
    password VARCHAR(255),
    face_image LONGBLOB,
    position VARCHAR(100) DEFAULT 'Employee',
    is_admin TINYINT DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT Exists rota (
    id INT NOT NULL AUTO_INCREMENT,
    rota_image LONGBLOB,
    uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT Exists notifications (
    id INT NOT NULL AUTO_INCREMENT,
    message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_read TINYINT DEFAULT 0,
    read_at TIMESTAMP NULL,
    mark_done TINYINT DEFAULT 0,
    mark_done_at TIMESTAMP NULL,
    user_id INT,
    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT Exists daily_updates (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT,
    update_message TEXT,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_verified TINYINT DEFAULT 0,
    verification_status ENUM('Pending', 'Approved', 'Rejected') DEFAULT 'Pending',
    verified_at TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT Exists attendance (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT,
    login_time DATETIME,
    logout_time DATETIME,
    login_photo_path VARCHAR(255),
    logout_photo_path VARCHAR(255),
    login_latitude FLOAT,
    login_longitude FLOAT,
    logout_latitude FLOAT,
    logout_longitude FLOAT,
    daily_status_submitted TINYINT DEFAULT 0,
    admin_verified TINYINT DEFAULT 0,
    attendance_status ENUM('Present', 'Absent') DEFAULT 'Absent',
    daily_status TEXT,
    status TEXT,
    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

