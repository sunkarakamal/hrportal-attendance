from flask import Flask, request, render_template, jsonify, session, redirect, url_for, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import Error
import os
import cv2
import geocoder
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import face_recognition
import numpy as np
import smtplib
from email.mime.text import MIMEText
import random
import base64
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "default_secret_key_123")  # Fallback for development

# MySQL Configuration
db_config = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "jhaishna"),
    "database": os.environ.get("DB_NAME", "gps_face_db"),
    "port": int(os.environ.get("DB_PORT", 3306))
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        if conn.is_connected():
            logging.info("Successfully established database connection")
            return conn
        else:
            logging.error("Failed to establish database connection")
            return None
    except Error as err:
        logging.error(f"Database connection failed: {err}")
        flash(f"Database connection failed: {err}", "error")
        return None

# Database initialization
def init_db():
    conn = get_db_connection()
    if not conn:
        logging.error("Cannot initialize database: No connection")
        return
    try:
        cursor = conn.cursor()
        logging.info("Initializing database schema")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE,
                email VARCHAR(100) UNIQUE,
                password VARCHAR(255),
                face_image LONGBLOB,
                position VARCHAR(100) DEFAULT 'Employee',
                is_admin BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                login_time DATETIME,
                logout_time DATETIME,
                login_photo_path VARCHAR(255),
                logout_photo_path VARCHAR(255),
                login_latitude FLOAT,
                login_longitude FLOAT,
                logout_latitude FLOAT,
                logout_longitude FLOAT,
                daily_status_submitted TINYINT(1) DEFAULT 0,
                admin_verified TINYINT(1) DEFAULT 0,
                attendance_status ENUM('Present', 'Absent') DEFAULT 'Absent',
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rota (
                id INT AUTO_INCREMENT PRIMARY KEY,
                rota_image LONGBLOB,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id INT,
                is_read BOOLEAN DEFAULT 0,
                read_at TIMESTAMP NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_updates (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                update_message TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verification_status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        conn.commit()
        logging.info("Database schema initialized successfully")
    except Error as err:
        logging.error(f"Error initializing database: {err}")
        flash(f"Error initializing database: {err}", "error")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# Jinja2 custom filters
app.jinja_env.filters['strftime'] = lambda dt, fmt: dt.strftime(fmt) if dt else 'N/A'

@app.route('/')
def home():
    logging.info("Accessing home route, redirecting to login")
    return redirect(url_for('login'))


# ==================== LOGIN ROUTE (UPDATED) ====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        logging.info(f"Login attempt: email={email}")

        if not email or not password:
            flash("Email and password are required", "error")
            return render_template('login.html')

        conn = get_db_connection()
        if not conn:
            flash("Database connection failed", "error")
            return render_template('login.html')
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['is_admin'] = bool(user['is_admin'])
                session.pop('acting_as_user', None)  # Reset mode on new login
                session.permanent = True
                logging.info(f"Session after login: {dict(session)}")

                if user['is_admin']:
                    flash("Login successful! Choose your role.", "success")
                    return redirect(url_for('login') + '?show_modal=true')
                else:
                    flash("Login successful!", "success")
                    return redirect(url_for('dashboard'))
            else:
                flash("Invalid credentials", "error")
        except Exception as e:
            logging.error(f"Error in login: {str(e)}")
            flash(f"Login error: {str(e)}", "error")
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()
    else:
        # GET request: show modal if needed
        pass

    return render_template('login.html')


# NEW: Handle admin dashboard choice
@app.route('/choose_dashboard', methods=['POST'])
def choose_dashboard():
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({"success": False})

    role = request.form.get('role')
    if role == 'admin':
        session.pop('acting_as_user', None)
        return jsonify({"success": True, "redirect": url_for('admin')})
    elif role == 'user':
        session['acting_as_user'] = True
        return jsonify({"success": True, "redirect": url_for('dashboard')})
    else:
        return jsonify({"success": False})


# ==================== DASHBOARD (FIXED) ====================
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash("Please login to continue", "error")
        return redirect(url_for('login'))

    # Block admin unless acting as user
    if session.get('is_admin') and not session.get('acting_as_user'):
        flash("Admins must choose a role", "error")
        return redirect(url_for('login') + '?show_modal=true')

    conn = get_db_connection()
    if not conn:
        logging.error("No database connection for dashboard")
        flash("Database connection failed", "error")
        return render_template('dashboard.html', last_login=None, last_logout=None, rota_image_base64=None)

    cursor = conn.cursor(dictionary=True)
    try:
        logging.info(f"Fetching user data for user_id: {session['user_id']}")
        cursor.execute("SELECT email, face_image, position, created_at FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        if not user:
            flash("User not found", "error")
            logging.error(f"User not found: user_id={session['user_id']}")
            return redirect(url_for('logout'))

        logging.info(f"Fetching today's attendance for user_id: {session['user_id']}")
        cursor.execute("SELECT login_time, logout_time, daily_status_submitted FROM attendance WHERE user_id = %s AND DATE(login_time) = CURDATE()", (session['user_id'],))
        today_attendance = cursor.fetchone()
        can_login = not bool(today_attendance)
        daily_status_submitted = bool(today_attendance and today_attendance['daily_status_submitted'])
        attendance_submitted = bool(today_attendance and today_attendance['logout_time'])
        logging.info(f"Today's attendance: {'Found' if today_attendance else 'Not found'}, can_login={can_login}, daily_status_submitted={daily_status_submitted}, attendance_submitted={attendance_submitted}")

        logging.info(f"Fetching last attendance for user_id: {session['user_id']}")
        cursor.execute("""
            SELECT login_time, logout_time 
            FROM attendance 
            WHERE user_id = %s 
            ORDER BY login_time DESC 
            LIMIT 1
        """, (session['user_id'],))
        last_attendance = cursor.fetchone()
        logging.info(f"Last attendance: {'Found' if last_attendance else 'Not found'}")

        logging.info(f"Fetching 30-day attendance history for user_id: {session['user_id']}")
        cursor.execute("""
            SELECT DATE(login_time) as date, attendance_status 
            FROM attendance 
            WHERE user_id = %s AND login_time >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        """, (session['user_id'],))
        attendance_data = cursor.fetchall()
        attendance_records = []
        for i in range(30):
            date = (datetime.now() - timedelta(days=i)).date()
            record = next((r for r in attendance_data if r['date'] == date), None)
            attendance_records.append({'date': date, 'present': record['attendance_status'] == 'Present' if record else False})
        logging.info(f"Retrieved {len(attendance_records)} attendance records")

        logging.info(f"Fetching notifications for user_id: {session['user_id']}")
        cursor.execute("SELECT message, created_at FROM notifications WHERE user_id = %s ORDER BY created_at DESC", (session['user_id'],))
        notifications = cursor.fetchall()
        logging.info(f"Retrieved {len(notifications)} notifications")

        logging.info(f"Fetching daily updates for user_id: {session['user_id']}")
        cursor.execute("SELECT update_message, submitted_at, verification_status FROM daily_updates WHERE user_id = %s ORDER BY submitted_at DESC", (session['user_id'],))
        daily_updates = cursor.fetchall()
        logging.info(f"Retrieved {len(daily_updates)} daily updates")

        logging.info("Fetching latest rota image")
        cursor.execute("SELECT rota_image FROM rota ORDER BY uploaded_at DESC LIMIT 1")
        rota = cursor.fetchone()
        rota_image_base64 = base64.b64encode(rota['rota_image']).decode('utf-8') if rota and rota['rota_image'] else None
        logging.info(f"Rota image: {'Found' if rota else 'Not found'}")

        user_face_image_base64 = base64.b64encode(user['face_image']).decode('utf-8') if user['face_image'] else None
        logging.info(f"User face image: {'Found' if user['face_image'] else 'Not found'}")

        logging.info("Rendering dashboard template")
        return render_template('dashboard.html',
                              user_email=user['email'],
                              user_face_image_base64=user_face_image_base64,
                              user_position=user['position'],
                              created_at=user['created_at'],
                              last_login=last_attendance['login_time'] if last_attendance else None,
                              last_logout=last_attendance['logout_time'] if last_attendance else None,
                              can_login=can_login,
                              daily_status_submitted=daily_status_submitted,
                              attendance_submitted=attendance_submitted,
                              attendance_records=attendance_records,
                              notifications=notifications,
                              daily_updates=daily_updates,
                              rota_image_base64=rota_image_base64)
    except Exception as e:
        logging.error(f"Dashboard error: {str(e)}")
        flash(f"Error loading dashboard: {str(e)}", "error")
        return render_template('dashboard.html', last_login=None, last_logout=None, rota_image_base64=None)
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


# ==================== ALL OTHER ROUTES (UNCHANGED) ====================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        face_image = request.files.get('face_image')
        logging.info(f"Register attempt: username={username}, email={email}")

        if not all([username, email, password, face_image]):
            flash("All fields are required", "error")
            logging.error("Missing required fields")
            return render_template('register.html')

        face_image_data = face_image.read()
        if not face_image_data:
            flash("Invalid face image", "error")
            logging.error("Invalid or empty face image")
            return render_template('register.html')

        conn = get_db_connection()
        if not conn:
            logging.error("No database connection for register")
            flash("Database connection failed", "error")
            return render_template('register.html')

        try:
            cursor = conn.cursor()
            hashed_password = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO users (username, email, password, face_image, is_admin) VALUES (%s, %s, %s, %s, %s)",
                (username, email, hashed_password, face_image_data, 0)
            )
            conn.commit()
            flash("Registration successful! Please login.", "success")
            logging.info(f"User {username} registered successfully")
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            flash("Username or email already exists", "error")
            logging.error(f"Username or email already exists: {username}, {email}")
        except Exception as e:
            flash(f"Registration error: {str(e)}", "error")
            logging.error(f"Registration error: {str(e)}")
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()
    logging.info("Rendering register page")
    return render_template('register.html')

# ... [Keep ALL other routes exactly as they were: forgot_password, verify_otp, reset_password, login_photo, logout_photo, update_profile, admin_update_user, upload_rota, send_notification, check_notifications, admin, update_attendance_status, view_excel, export_page, export, logout] ...

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        logging.info(f"Forgot password request for email: {email}")
        if not email:
            flash("Email is required", "error")
            logging.error("Missing email for forgot password")
            return render_template('forgot_password.html')

        conn = get_db_connection()
        if not conn:
            logging.error("No database connection for forgot_password")
            flash("Database connection failed", "error")
            return render_template('forgot_password.html')
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            logging.info(f"User lookup for forgot password: {'Found' if user else 'Not found'}")
            if user:
                otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
                session['otp'] = otp
                session['reset_email'] = email
                session['otp_sent'] = True
                logging.info(f"Generated OTP: {otp}")

                sender = os.environ.get("SMTP_SENDER", "your_email@gmail.com")
                smtp_password = os.environ.get("SMTP_PASSWORD", "your_app_password")
                smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
                smtp_port = int(os.environ.get("SMTP_PORT", 587))

                msg = MIMEText(f"Your OTP for password reset is: {otp}\nValid for 10 minutes.")
                msg['Subject'] = "Password Reset OTP"
                msg['From'] = sender
                msg['To'] = email

                try:
                    with smtplib.SMTP(smtp_server, smtp_port) as server:
                        server.starttls()
                        server.login(sender, smtp_password)
                        server.send_message(msg)
                    flash("OTP sent to your email!", "success")
                    logging.info(f"OTP email sent to: {email}")
                    return redirect(url_for('forgot_password'))
                except smtplib.SMTPAuthenticationError:
                    flash("Failed to authenticate with email server", "error")
                    logging.error("SMTP authentication failed: Check email and app password")
                    return render_template('forgot_password.html')
                except smtplib.SMTPException as e:
                    flash(f"Failed to send email: {str(e)}", "error")
                    logging.error(f"SMTP error: {str(e)}")
                    return render_template('forgot_password.html')
                except Exception as e:
                    flash(f"Unexpected error sending email: {str(e)}", "error")
                    logging.error(f"Unexpected error in SMTP: {str(e)}")
                    return render_template('forgot_password.html')
            else:
                flash("Email not found", "error")
                logging.error(f"Email not found: {email}")
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()
    logging.info("Rendering forgot_password page")
    return render_template('forgot_password.html')

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    otp = request.form.get('otp')
    logging.info(f"Verifying OTP: {otp}")
    if not otp:
        flash("OTP is required", "error")
        logging.error("Missing OTP")
        return redirect(url_for('forgot_password'))

    if otp == session.get('otp'):
        session.pop('otp', None)
        session['otp_verified'] = True
        flash("OTP verified!", "success")
        logging.info("OTP verified successfully")
        return redirect(url_for('reset_password'))
    else:
        flash("Invalid OTP", "error")
        logging.error("Invalid OTP provided")
        return redirect(url_for('forgot_password'))

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if not session.get('otp_verified'):
        logging.error("OTP not verified, redirecting to login")
        flash("Please verify OTP first", "error")
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        if not new_password:
            flash("New password is required", "error")
            logging.error("Missing new password")
            return render_template('reset_password.html')

        logging.info(f"Resetting password for email: {session.get('reset_email')}")
        conn = get_db_connection()
        if not conn:
            logging.error("No database connection for reset_password")
            flash("Database connection failed", "error")
            return render_template('reset_password.html')
        try:
            cursor = conn.cursor()
            hashed_password = generate_password_hash(new_password)
            cursor.execute("UPDATE users SET password = %s WHERE email = %s", (hashed_password, session.get('reset_email')))
            conn.commit()
            session.pop('reset_email', None)
            session.pop('otp_verified', None)
            session.pop('otp_sent', None)
            flash("Password reset successful! Please login.", "success")
            logging.info("Password reset successful")
            return redirect(url_for('login'))
        except Exception as e:
            logging.error(f"Reset password error: {str(e)}")
            flash(f"Reset password error: {str(e)}", "error")
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()
    logging.info("Rendering reset_password page")
    return render_template('reset_password.html')

@app.route('/login_photo', methods=['POST'])
def login_photo():
    if 'user_id' not in session:
        logging.error("Not logged in for login_photo")
        return jsonify({"success": False, "message": "Not logged in"})

    file = request.files.get('face_image')
    if not file:
        logging.error("No photo uploaded for login_photo")
        return jsonify({"success": False, "message": "No photo uploaded"})

    latitude = float(request.form.get('latitude', 0.0))
    longitude = float(request.form.get('longitude', 0.0))

    conn = get_db_connection()
    if not conn:
        logging.error("No database connection for login_photo")
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor(dictionary=True)
    try:
        logging.info(f"Fetching user face image for user_id: {session['user_id']}")
        cursor.execute("SELECT face_image FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()

        if not user or not user['face_image']:
            logging.error("No registered face image found")
            return jsonify({"success": False, "message": "No registered face image"})

        registered_image = face_recognition.load_image_file(BytesIO(user['face_image']))
        captured_image = face_recognition.load_image_file(file)
        registered_enc = face_recognition.face_encodings(registered_image)
        captured_enc = face_recognition.face_encodings(captured_image)

        if not registered_enc or not captured_enc or not face_recognition.compare_faces([registered_enc[0]], captured_enc[0])[0]:
            logging.error("Face verification failed for login")
            return jsonify({"success": False, "message": "Face verification failed"})

        uploads_dir = os.path.join(app.static_folder, 'Uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        login_time = datetime.now()
        login_photo_path = os.path.join(uploads_dir, f"{session['username']}_login_{login_time.strftime('%Y%m%d%H%M%S')}.jpg")
        file.save(login_photo_path)
        logging.info(f"Login photo saved: {login_photo_path}")

        logging.info(f"Login location: ({latitude}, {longitude})")

        cursor.execute("""
            INSERT INTO attendance (user_id, login_time, login_photo_path, login_latitude, login_longitude, attendance_status) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (session['user_id'], login_time, login_photo_path, latitude, longitude, 'Present'))
        conn.commit()

        with open(login_photo_path, 'rb') as image_file:
            login_photo_base64 = base64.b64encode(image_file.read()).decode('utf-8')

        logging.info("Login recorded successfully")
        return jsonify({
            "success": True,
            "message": "Login recorded",
            "login_photo": login_photo_base64
        })
    except Exception as e:
        logging.error(f"Login photo error: {str(e)}")
        return jsonify({"success": False, "message": f"Error processing login: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/submit_daily_status', methods=['POST'])
def submit_daily_status():
    if 'user_id' not in session:
        logging.error("Not logged in for submit_daily_status")
        return jsonify({"success": False, "message": "Not logged in"})

    daily_status = request.form.get('daily_status')
    if not daily_status:
        logging.error("Daily status is required")
        return jsonify({"success": False, "message": "Daily status is required"})

    conn = get_db_connection()
    if not conn:
        logging.error("No database connection for submit_daily_status")
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor()
    try:
        logging.info(f"Submitting daily status for user_id: {session['user_id']}")
        cursor.execute("""
            INSERT INTO daily_updates (user_id, update_message) 
            VALUES (%s, %s)
        """, (session['user_id'], daily_status))
        cursor.execute("""
            UPDATE attendance 
            SET daily_status_submitted = 1 
            WHERE user_id = %s AND DATE(login_time) = CURDATE() AND logout_time IS NULL
        """, (session['user_id'],))
        conn.commit()
        logging.info("Daily status submitted successfully")
        return jsonify({"success": True, "message": "Daily status submitted"})
    except Exception as e:
        logging.error(f"Submit daily status error: {str(e)}")
        return jsonify({"success": False, "message": f"Error submitting daily status: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/logout_photo', methods=['POST'])
def logout_photo():
    if 'user_id' not in session:
        logging.error("Not logged in for logout_photo")
        return jsonify({"success": False, "message": "Not logged in"})

    file = request.files.get('face_image')
    if not file:
        logging.error("No photo uploaded for logout_photo")
        return jsonify({"success": False, "message": "No photo uploaded"})

    latitude = float(request.form.get('latitude', 0.0))
    longitude = float(request.form.get('longitude', 0.0))

    conn = get_db_connection()
    if not conn:
        logging.error("No database connection for logout_photo")
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor(dictionary=True)
    try:
        logging.info(f"Checking daily status for user_id: {session['user_id']}")
        cursor.execute("SELECT daily_status_submitted FROM attendance WHERE user_id = %s AND DATE(login_time) = CURDATE()", (session['user_id'],))
        attendance = cursor.fetchone()
        if not attendance or not attendance['daily_status_submitted']:
            logging.error("Daily status not submitted")
            return jsonify({"success": False, "message": "Please submit your daily status report before logging out"})

        logging.info(f"Fetching user face image for user_id: {session['user_id']}")
        cursor.execute("SELECT face_image FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()

        if not user or not user['face_image']:
            logging.error("No registered face image found")
            return jsonify({"success": False, "message": "No registered face image"})

        registered_image = face_recognition.load_image_file(BytesIO(user['face_image']))
        captured_image = face_recognition.load_image_file(file)
        registered_enc = face_recognition.face_encodings(registered_image)
        captured_enc = face_recognition.face_encodings(captured_image)

        if not registered_enc or not captured_enc or not face_recognition.compare_faces([registered_enc[0]], captured_enc[0])[0]:
            logging.error("Face verification failed for logout")
            return jsonify({"success": False, "message": "Face verification failed"})

        uploads_dir = os.path.join(app.static_folder, 'Uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        logout_time = datetime.now()
        logout_photo_path = os.path.join(uploads_dir, f"{session['username']}_logout_{logout_time.strftime('%Y%m%d%H%M%S')}.jpg")
        file.save(logout_photo_path)
        logging.info(f"Logout photo saved: {logout_photo_path}")

        logging.info(f"Logout location: ({latitude}, {longitude})")

        cursor.execute("""
            UPDATE attendance 
            SET logout_time = %s, logout_photo_path = %s, logout_latitude = %s, logout_longitude = %s 
            WHERE user_id = %s AND logout_time IS NULL 
            ORDER BY login_time DESC 
            LIMIT 1
        """, (logout_time, logout_photo_path, latitude, longitude, session['user_id']))
        conn.commit()

        with open(logout_photo_path, 'rb') as image_file:
            logout_photo_base64 = base64.b64encode(image_file.read()).decode('utf-8')

        logging.info("Logout recorded successfully")
        return jsonify({
            "success": True,
            "message": "Logout recorded",
            "logout_photo": logout_photo_base64
        })
    except Exception as e:
        logging.error(f"Logout photo error: {str(e)}")
        return jsonify({"success": False, "message": f"Error processing logout: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        logging.error("Not logged in for update_profile")
        return jsonify({"success": False, "message": "Not logged in"})

    email = request.form.get('email')
    face_image = request.files.get('face_image')
    position = request.form.get('position')
    logging.info(f"Updating profile for user_id: {session['user_id']}, email={email}, position={position}")

    if not any([email, face_image, position]):
        logging.error("No changes provided for profile update")
        return jsonify({"success": False, "message": "No changes provided"})

    conn = get_db_connection()
    if not conn:
        logging.error("No database connection for update_profile")
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor()
    try:
        updates = []
        params = []
        if email:
            updates.append("email = %s")
            params.append(email)
        if position:
            updates.append("position = %s")
            params.append(position)
        if face_image:
            face_image_data = face_image.read()
            if not face_image_data:
                logging.error("Invalid or empty face image")
                return jsonify({"success": False, "message": "Invalid face image"})
            updates.append("face_image = %s")
            params.append(face_image_data)

        params.append(session['user_id'])
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
        logging.info(f"Executing profile update query: {query}")
        cursor.execute(query, tuple(params))
        conn.commit()

        cursor.execute("SELECT username, email, position FROM users WHERE id = %s", (session['user_id'],))
        user_data = cursor.fetchone()
        session['username'] = user_data['username']
        session['email'] = user_data['email']
        session['position'] = user_data['position']
        logging.info("Profile updated successfully")
        return jsonify({"success": True, "message": "Profile updated"})
    except mysql.connector.IntegrityError:
        logging.error("Username or email already exists")
        return jsonify({"success": False, "message": "Email already exists"})
    except Exception as e:
        logging.error(f"Profile update error: {str(e)}")
        return jsonify({"success": False, "message": f"Error updating profile: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/admin_update_user/<int:user_id>', methods=['POST'])
def admin_update_user(user_id):
    if not session.get('is_admin'):
        logging.error("Access denied for admin_update_user")
        return jsonify({"success": False, "message": "Access denied"})

    username = request.form.get('username')
    email = request.form.get('email')
    position = request.form.get('position')
    face_image = request.files.get('face_image')
    logging.info(f"Admin updating user: user_id={user_id}, username={username}, email={email}")

    if not any([username, email, position, face_image]):
        logging.error("No changes provided for admin user update")
        return jsonify({"success": False, "message": "No changes provided"})

    conn = get_db_connection()
    if not conn:
        logging.error("No database connection for admin_update_user")
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor()
    try:
        updates = []
        params = []
        if username:
            updates.append("username = %s")
            params.append(username)
        if email:
            updates.append("email = %s")
            params.append(email)
        if position:
            updates.append("position = %s")
            params.append(position)
        if face_image:
            face_image_data = face_image.read()
            if not face_image_data:
                logging.error("Invalid or empty face image")
                return jsonify({"success": False, "message": "Invalid face image"})
            updates.append("face_image = %s")
            params.append(face_image_data)

        params.append(user_id)
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
        logging.info(f"Executing admin user update query: {query}")
        cursor.execute(query, tuple(params))
        conn.commit()
        logging.info("User updated by admin")
        return jsonify({"success": True, "message": "User updated"})
    except mysql.connector.IntegrityError:
        logging.error("Username or email already exists for admin update")
        return jsonify({"success": False, "message": "Username or email already exists"})
    except Exception as e:
        logging.error(f"Admin user update error: {str(e)}")
        return jsonify({"success": False, "message": f"Error updating user: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/upload_rota', methods=['POST'])
def upload_rota():
    if not session.get('is_admin'):
        logging.error("Access denied for upload_rota")
        return jsonify({"success": False, "message": "Access denied"})

    file = request.files.get('rota_image')
    if not file:
        logging.error("No file uploaded for rota")
        return jsonify({"success": False, "message": "No file uploaded"})

    rota_image_data = file.read()
    if not rota_image_data:
        logging.error("Invalid or empty rota image")
        return jsonify({"success": False, "message": "Invalid rota image"})

    conn = get_db_connection()
    if not conn:
        logging.error("No database connection for upload_rota")
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO rota (rota_image) VALUES (%s)", (rota_image_data,))
        conn.commit()
        logging.info("Rota uploaded successfully")
        return jsonify({"success": True, "message": "Rota uploaded successfully"})
    except Exception as e:
        logging.error(f"Rota upload error: {str(e)}")
        return jsonify({"success": False, "message": f"Error uploading rota: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/send_notification', methods=['POST'])
def send_notification():
    if not session.get('is_admin'):
        logging.error("Access denied for send_notification")
        return jsonify({"success": False, "message": "Access denied"})

    message = request.form.get('message')
    if not message:
        logging.error("No message provided for notification")
        return jsonify({"success": False, "message": "No message provided"})

    conn = get_db_connection()
    if not conn:
        logging.error("No database connection for send_notification")
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor(dictionary=True)
    try:
        logging.info("Fetching non-admin users for notification")
        cursor.execute("SELECT id FROM users WHERE is_admin = 0")
        users = cursor.fetchall()
        if not users:
            logging.error("No non-admin users found")
            return jsonify({"success": False, "message": "No non-admin users found"})

        for user in users:
            logging.info(f"Sending notification to user_id: {user['id']}")
            cursor.execute("INSERT INTO notifications (message, user_id) VALUES (%s, %s)", (message, user['id']))
        conn.commit()
        logging.info("Notifications sent successfully")
        return jsonify({"success": True, "message": "Notification sent to all users"})
    except Exception as e:
        logging.error(f"Notification error: {str(e)}")
        return jsonify({"success": False, "message": f"Error sending notification: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/check_notifications', methods=['GET'])
def check_notifications():
    if 'user_id' not in session or session.get('is_admin'):
        logging.error("Access denied or admin user for check_notifications")
        return jsonify({"success": False, "message": ""})

    conn = get_db_connection()
    if not conn:
        logging.error("No database connection for check_notifications")
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor(dictionary=True)
    try:
        logging.info(f"Checking notifications for user_id: {session['user_id']}")
        cursor.execute("""
            SELECT id, message 
            FROM notifications 
            WHERE user_id = %s AND is_read = 0 
            ORDER BY created_at DESC 
            LIMIT 1
        """, (session['user_id'],))
        notification = cursor.fetchone()
        if notification:
            logging.info(f"Marking notification as read: id={notification['id']}")
            cursor.execute("UPDATE notifications SET is_read = 1, read_at = NOW() WHERE id = %s", (notification['id'],))
            conn.commit()
            logging.info(f"Notification read: {notification['message']}")
            return jsonify({"success": True, "message": notification['message']})
        logging.info("No unread notifications found")
        return jsonify({"success": False, "message": ""})
    except Exception as e:
        logging.error(f"Check notifications error: {str(e)}")
        return jsonify({"success": False, "message": f"Error checking notifications: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/admin')
def admin():
    logging.info(f"Accessing admin route with session: {dict(session)}")
    if not session.get('is_admin'):
        flash("Access denied", "error")
        logging.error("Access denied for admin route")
        return redirect(url_for('login'))

    view = request.args.get('view', 'daily')
    search_query = request.args.get('search', '')
    logging.info(f"Admin view: {view}, search_query: {search_query}")

    conn = get_db_connection()
    if not conn:
        logging.error("No database connection for admin")
        flash("Database connection failed", "error")
        return render_template('admin.html', data=[], view=view, admin_profile=None, users=[], all_attendance=[], rota_image_base64=None)

    cursor = conn.cursor(dictionary=True)
    try:
        logging.info(f"Fetching admin profile for user_id: {session['user_id']}")
        cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
        admin_profile = cursor.fetchone()
        admin_profile['face_image_base64'] = base64.b64encode(admin_profile['face_image']).decode('utf-8') if admin_profile and admin_profile['face_image'] else None
        logging.info(f"Admin profile image: {'Found' if admin_profile and admin_profile['face_image'] else 'Not found'}")

        logging.info("Fetching non-admin users")
        cursor.execute("SELECT id, username, email, position, face_image FROM users WHERE is_admin = 0")
        users_raw = cursor.fetchall()
        users = []
        for user in users_raw:
            user['face_image_base64'] = base64.b64encode(user['face_image']).decode('utf-8') if user['face_image'] else None
            users.append(user)
        logging.info(f"Retrieved {len(users)} non-admin users")

        if view == 'daily':
            query = """
                SELECT u.username, u.position, a.id as attendance_id, a.user_id, a.login_time, a.logout_time, 
                       a.login_latitude, a.login_longitude, a.logout_latitude, a.logout_longitude,
                       a.daily_status_submitted, a.attendance_status,
                       TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
                FROM users u LEFT JOIN attendance a ON u.id = a.user_id
                WHERE DATE(a.login_time) = CURDATE()
                ORDER BY a.login_time DESC
            """
        elif view == 'weekly':
            query = """
                SELECT u.username, u.position, a.id as attendance_id, a.user_id, a.login_time, a.logout_time, 
                       a.login_latitude, a.login_longitude, a.logout_latitude, a.logout_longitude,
                       a.daily_status_submitted, a.attendance_status,
                       TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
                FROM users u LEFT JOIN attendance a ON u.id = a.user_id
                WHERE WEEK(a.login_time) = WEEK(CURDATE())
                ORDER BY a.login_time DESC
            """
        elif view == 'monthly':
            query = """
                SELECT u.username, u.position, a.id as attendance_id, a.user_id, a.login_time, a.logout_time, 
                       a.login_latitude, a.login_longitude, a.logout_latitude, a.logout_longitude,
                       a.daily_status_submitted, a.attendance_status,
                       TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
                FROM users u LEFT JOIN attendance a ON u.id = a.user_id
                WHERE MONTH(a.login_time) = MONTH(CURDATE())
                ORDER BY a.login_time DESC
            """
        else:  # yearly
            query = """
                SELECT u.username, u.position, a.id as attendance_id, a.user_id, a.login_time, a.logout_time, 
                       a.login_latitude, a.login_longitude, a.logout_latitude, a.logout_longitude,
                       a.daily_status_submitted, a.attendance_status,
                       TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
                FROM users u LEFT JOIN attendance a ON u.id = a.user_id
                WHERE YEAR(a.login_time) = YEAR(CURDATE())
                ORDER BY a.login_time DESC
            """
        logging.info(f"Executing attendance query for view: {view}")
        cursor.execute(query)
        data = cursor.fetchall()

        for record in data:
            if record['seconds_worked']:
                hours = record['seconds_worked'] // 3600
                minutes = (record['seconds_worked'] % 3600) // 60
                seconds = record['seconds_worked'] % 60
                record['hours_worked'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                record['color'] = 'red' if hours < 9 else 'green'
            else:
                record['hours_worked'] = "N/A"
                record['color'] = 'black'
        logging.info(f"Processed {len(data)} attendance records for view: {view}")

        if search_query:
            logging.info(f"Executing search query: {search_query}")
            cursor.execute("""
                SELECT u.username, u.position, a.id as attendance_id, a.user_id, a.login_time, a.logout_time, 
                       a.login_latitude, a.login_longitude, a.logout_latitude, a.logout_longitude,
                       a.daily_status_submitted, a.attendance_status,
                       TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
                FROM users u LEFT JOIN attendance a ON u.id = a.user_id
                WHERE u.username LIKE %s
                ORDER BY a.login_time DESC
            """, (f"%{search_query}%",))
        else:
            logging.info("Fetching all attendance records")
            cursor.execute("""
                SELECT u.username, u.position, a.id as attendance_id, a.user_id, a.login_time, a.logout_time, 
                       a.login_latitude, a.login_longitude, a.logout_latitude, a.logout_longitude,
                       a.daily_status_submitted, a.attendance_status,
                       TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
                FROM users u LEFT JOIN attendance a ON u.id = a.user_id
                ORDER BY a.login_time DESC
            """)
        all_attendance = cursor.fetchall()

        for record in all_attendance:
            if record['seconds_worked']:
                hours = record['seconds_worked'] // 3600
                minutes = (record['seconds_worked'] % 3600) // 60
                seconds = record['seconds_worked'] % 60
                record['hours_worked'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                record['color'] = 'red' if hours < 9 else 'green'
            else:
                record['hours_worked'] = "N/A"
                record['color'] = 'black'
        logging.info(f"Processed {len(all_attendance)} total attendance records")

        logging.info("Fetching latest rota image for admin")
        cursor.execute("SELECT rota_image FROM rota ORDER BY uploaded_at DESC LIMIT 1")
        rota = cursor.fetchone()
        rota_image_base64 = base64.b64encode(rota['rota_image']).decode('utf-8') if rota and rota['rota_image'] else None
        logging.info(f"Rota image: {'Found' if rota else 'Not found'}")

        logging.info("Fetching read notifications")
        cursor.execute("""
            SELECT n.id, n.message, n.created_at, n.read_at, u.username 
            FROM notifications n 
            JOIN users u ON n.user_id = u.id 
            WHERE n.is_read = 1 
            ORDER BY n.read_at DESC
        """)
        read_notifications = cursor.fetchall()
        logging.info(f"Retrieved {len(read_notifications)} read notifications")

        logging.info("Rendering admin template")
        return render_template('admin.html', data=data, view=view, admin_profile=admin_profile, users=users, all_attendance=all_attendance,
                              search_query=search_query, rota_image_base64=rota_image_base64, read_notifications=read_notifications)
    except Exception as e:
        logging.error(f"Admin route error: {str(e)}")
        flash(f"Error loading admin page: {str(e)}", "error")
        return render_template('admin.html', data=[], view=view, admin_profile=None, users=[], all_attendance=[], rota_image_base64=None)
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/update_attendance_status/<int:attendance_id>', methods=['POST'])
def update_attendance_status(attendance_id):
    if not session.get('is_admin'):
        logging.error("Access denied for update_attendance_status")
        return jsonify({"success": False, "message": "Access denied"})

    status = request.form.get('status')
    logging.info(f"Updating attendance status: attendance_id={attendance_id}, status={status}")
    if status not in ['Present', 'Absent']:
        logging.error("Invalid status provided")
        return jsonify({"success": False, "message": "Invalid status"})

    conn = get_db_connection()
    if not conn:
        logging.error("No database connection for update_attendance_status")
        return jsonify({"success": False, "message": "Database error"})

    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE attendance SET attendance_status = %s WHERE id = %s", (status, attendance_id))
        conn.commit()
        logging.info("Attendance status updated")
        return jsonify({"success": True, "message": "Attendance status updated"})
    except Exception as e:
        logging.error(f"Update attendance status error: {str(e)}")
        return jsonify({"success": False, "message": f"Error updating attendance status: {str(e)}"})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/view_excel')
def view_excel():
    if not session.get('is_admin'):
        flash("Access denied", "error")
        logging.error("Access denied for view_excel")
        return redirect(url_for('login'))

    conn = get_db_connection()
    if not conn:
        flash("Database connection failed", "error")
        logging.error("No database connection for view_excel")
        return render_template('view_excel.html', table="")

    cursor = conn.cursor(dictionary=True)
    try:
        logging.info("Fetching attendance data for Excel view")
        cursor.execute("""
            SELECT u.username, a.login_time, a.logout_time, a.daily_status_submitted, a.attendance_status,
                   TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
            FROM users u LEFT JOIN attendance a ON u.id = a.user_id
        """)
        data = cursor.fetchall()
        if not data:
            flash("No attendance data available", "warning")
            logging.warning("No attendance data available")
            return render_template('view_excel.html', table="")

        for record in data:
            if record['seconds_worked']:
                hours = record['seconds_worked'] // 3600
                minutes = (record['seconds_worked'] % 3600) // 60
                seconds = record['seconds_worked'] % 60
                record['hours_worked'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                record['hours_worked'] = "N/A"
        logging.info(f"Processed {len(data)} attendance records for Excel view")

        df = pd.DataFrame(data)[['username', 'login_time', 'logout_time', 'daily_status_submitted', 'attendance_status', 'hours_worked']]
        html_table = df.to_html(index=False, classes='table table-striped')
        logging.info("Rendering Excel view template")
        return render_template('view_excel.html', table=html_table)
    except Exception as e:
        flash(f"Error generating table: {str(e)}", "error")
        logging.error(f"Error generating Excel table: {str(e)}")
        return render_template('view_excel.html', table="")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/export_page')
def export_page():
    if not session.get('is_admin'):
        flash("Access denied", "error")
        logging.error("Access denied for export_page")
        return redirect(url_for('login'))
    logging.info("Rendering export page")
    return render_template('export.html')

@app.route('/export')
def export():
    if not session.get('is_admin'):
        flash("Access denied", "error")
        logging.error("Access denied for export")
        return redirect(url_for('login'))

    conn = get_db_connection()
    if not conn:
        flash("Database connection failed", "error")
        logging.error("No database connection for export")
        return redirect(url_for('admin'))

    cursor = conn.cursor(dictionary=True)
    try:
        logging.info("Fetching attendance data for Excel export")
        cursor.execute("""
            SELECT u.username, a.login_time, a.logout_time, a.daily_status_submitted, a.attendance_status,
                   TIMESTAMPDIFF(SECOND, a.login_time, COALESCE(a.logout_time, NOW())) as seconds_worked
            FROM users u LEFT JOIN attendance a ON u.id = a.user_id
        """)
        data = cursor.fetchall()
        if not data:
            flash("No attendance data to export", "warning")
            logging.warning("No attendance data to export")
            return redirect(url_for('admin'))

        for record in data:
            if record['seconds_worked']:
                hours = record['seconds_worked'] // 3600
                minutes = (record['seconds_worked'] % 3600) // 60
                seconds = record['seconds_worked'] % 60
                record['hours_worked'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                record['hours_worked'] = "N/A"
        logging.info(f"Processed {len(data)} attendance records for export")

        df = pd.DataFrame(data)[['username', 'login_time', 'logout_time', 'daily_status_submitted', 'attendance_status', 'hours_worked']]
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Attendance', index=False)
            workbook = writer.book
            worksheet = writer.sheets['Attendance']
            worksheet.set_column('A:A', 20)
            worksheet.set_column('B:C', 20)
            worksheet.set_column('D:D', 30)
            worksheet.set_column('E:E', 15)
            worksheet.set_column('F:F', 15)
        output.seek(0)
        logging.info("Excel file generated successfully")
        return send_file(output, download_name='attendance.xlsx', as_attachment=True)
    except Exception as e:
        flash(f"Error generating Excel file: {str(e)}", "error")
        logging.error(f"Error generating Excel file: {str(e)}")
        return redirect(url_for('admin'))
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/logout')
def logout():
    logging.info("Logging out user, clearing session")
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for('login'))

if __name__ == '__main__':
    # Ensure uploads directory exists
    uploads_dir = os.path.join(app.static_folder, 'Uploads')
    os.makedirs(uploads_dir, exist_ok=True)
    logging.info("Creating uploads directory if not exists")
    
    # Initialize database
    init_db()
    
    # Start Flask app
    logging.info("Starting Flask application on port 8000")
    app.run(debug=False, host='0.0.0.0', port=8000)

