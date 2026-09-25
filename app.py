from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash, abort
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import psycopg2.extras
import os
import smtplib
from email.mime.text import MIMEText
import random
import json
import uuid

app = Flask(__name__)
app.secret_key = 'pune_smart_hospital_network_secret_key'

# --- SECURITY: PREVENT BROWSER CACHING ---
@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# --- EMAIL CONFIGURATION ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_EMAIL = "academicuse20@gmail.com" 
SMTP_PASSWORD = "ipsbxeigfnrwwavw"

def send_system_email(to_email, subject, body):
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = f"PICT Hospital Mainframe <{SMTP_EMAIL}>"
        msg['To'] = to_email

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
        server.quit()
    except Exception as e:
        print("\n" + "="*50)
        print(f"FAILED TO SEND EMAIL: {e}")
        print("="*50 + "\n")

# Vercel relies on long-polling fallback for WebSockets
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

HOSPITALS_SEED = [
    {
        "id": "manipal-baner",
        "name": "Manipal Hospitals Baner",
        "area": "Baner - Mahalunge Rd",
        "rating": "4.7",
        "contact": "+91 20 6813 8888",
        "image": "https://images.unsplash.com/photo-1587351021759-3e566b6af7cc?q=80&w=800&auto=format&fit=crop",
        "specialties": "Cardiology, Oncology, Neurosurgery, Renal Care"
    },
    {
        "id": "ruby-sasoon",
        "name": "Ruby Hall Clinic (Sasoon Road)",
        "area": "Sasoon Rd, Sangamvadi",
        "rating": "4.5",
        "contact": "+91 20 6645 5100",
        "image": "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?q=80&w=800&auto=format&fit=crop",
        "specialties": "Quaternary Care, ICU, Cardiology, Organ Transplant"
    },
    {
        "id": "ruby-pcmc",
        "name": "Ruby Hall Clinic PCMC",
        "area": "Pimple Saudagar",
        "rating": "3.7",
        "contact": "+91 20 2720 1717",
        "image": "https://images.unsplash.com/photo-1629909613654-28e377c37b09?q=80&w=800&auto=format&fit=crop",
        "specialties": "Outpatient Care, Day-Care Surgeries, Diagnostics"
    },
    {
        "id": "ruby-hinjawadi",
        "name": "Ruby Hall Clinic (Hinjawadi)",
        "area": "Phase 1, Hinjawadi",
        "rating": "3.8",
        "contact": "+91 20 6699 9999",
        "image": "https://images.unsplash.com/photo-1516549655169-df83a0774514?q=80&w=800&auto=format&fit=crop",
        "specialties": "Emergency Response, Trauma, Critical Care"
    },
    {
        "id": "ruby-wanowrie",
        "name": "Ruby Hall Clinic (Wanowrie)",
        "area": "Wanowrie, Pune",
        "rating": "4.4",
        "contact": "+91 20 6649 4949",
        "image": "https://images.unsplash.com/photo-1512678080530-7760d81faba6?q=80&w=800&auto=format&fit=crop",
        "specialties": "General Medicine, Diagnostics, Trauma"
    },
    {
        "id": "aditya-birla",
        "name": "Aditya Birla Memorial Hospital",
        "area": "Chinchwad, PCMC",
        "rating": "4.3",
        "contact": "+91 98811 23006",
        "image": "https://images.unsplash.com/photo-1586773860418-d37222d8fce3?q=80&w=800&auto=format&fit=crop",
        "specialties": "Tertiary Care, Oncology, High-Capacity ICU"
    },
    {
        "id": "sancheti",
        "name": "Sancheti Hospital",
        "area": "Shivajinagar",
        "rating": "4.6",
        "contact": "+91 88888 08845",
        "image": "https://images.unsplash.com/photo-1538108149393-fbbd81895907?q=80&w=800&auto=format&fit=crop",
        "specialties": "Orthopaedics, Joint Replacement, Spine, Trauma"
    },
    {
        "id": "sahyadri-deccan",
        "name": "Sahyadri Super Speciality Hospital",
        "area": "Deccan Gymkhana",
        "rating": "4.7",
        "contact": "+91 20 4713 8766",
        "image": "https://images.unsplash.com/photo-1505751172876-fa1923c5c528?q=80&w=800&auto=format&fit=crop",
        "specialties": "Neurosciences, Organ Transplants, Critical Care"
    },
    {
        "id": "apollo-swargate",
        "name": "Apollo Hospitals (Swargate)",
        "area": "Shankar Sheth Rd, Swargate",
        "rating": "4.6",
        "contact": "+91 80 6297 2814",
        "image": "https://images.unsplash.com/photo-1587351021759-3e566b6af7cc?q=80&w=800&auto=format&fit=crop",
        "specialties": "Quaternary Care, Robotic Surgery, Neuro-ICU"
    },
    {
        "id": "apollo-spectra",
        "name": "Apollo Spectra Hospitals",
        "area": "Sadashiv Peth",
        "rating": "4.6",
        "contact": "+91 40 6914 6071",
        "image": "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?q=80&w=800&auto=format&fit=crop",
        "specialties": "Short-Stay Surgeries, General Medicine, ENT"
    }
]

def get_db_connection():
    # Vercel injects this automatically when you attach a Postgres DB
    conn = psycopg2.connect(os.environ.get('POSTGRES_URL', ''))
    return conn

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hospitals (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                area TEXT NOT NULL,
                rating TEXT,
                contact TEXT,
                image TEXT,
                specialties TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staff (
                id SERIAL PRIMARY KEY,
                hospital_id TEXT NOT NULL REFERENCES hospitals(id),
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                name TEXT,
                email TEXT,
                staff_id TEXT,
                status TEXT DEFAULT 'pending',
                assigned_floors TEXT DEFAULT '[]',
                UNIQUE(hospital_id, username)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS beds (
                hospital_id TEXT NOT NULL REFERENCES hospitals(id),
                bed_id TEXT NOT NULL,
                floor_num TEXT,
                floor_name TEXT,
                bed_type TEXT,
                status TEXT,
                patient_name TEXT,
                patient_age TEXT,
                diagnosis TEXT,
                PRIMARY KEY (hospital_id, bed_id)
            )
        ''')
        
        for h in HOSPITALS_SEED:
            cursor.execute('''
                INSERT INTO hospitals (id, name, area, rating, contact, image, specialties)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET 
                name=EXCLUDED.name, area=EXCLUDED.area, rating=EXCLUDED.rating, 
                contact=EXCLUDED.contact, image=EXCLUDED.image, specialties=EXCLUDED.specialties
            ''', (h['id'], h['name'], h['area'], h['rating'], h['contact'], h['image'], h['specialties']))
            
            hashed_pw = generate_password_hash('password123')
            cursor.execute('''
                INSERT INTO staff (hospital_id, username, password, name, email, staff_id, status, assigned_floors)
                VALUES (%s, 'admin', %s, 'Chief Nursing Officer', %s, 'ADMIN-001', 'approved', '[]')
                ON CONFLICT (hospital_id, username) DO NOTHING
            ''', (h['id'], hashed_pw, f"admin@{h['id']}.hospital.in"))
            
            cursor.execute('SELECT COUNT(*) FROM beds WHERE hospital_id = %s', (h['id'],))
            if cursor.fetchone()[0] == 0:
                sample_beds = [
                    (h['id'], 'ICU-101', '1', '1st Floor - Intensive Care', 'Ventilator', 'Available', '', '', ''),
                    (h['id'], 'ICU-102', '1', '1st Floor - Intensive Care', 'Oxygen Bed', 'Occupied', 'Ramesh P.', '58', 'Acute Respiratory'),
                    (h['id'], 'GEN-201', '2', '2nd Floor - General Ward', 'Standard Bed', 'Available', '', '', ''),
                    (h['id'], 'GEN-202', '2', '2nd Floor - General Ward', 'Standard Bed', 'Cleaning', '', '', '')
                ]
                cursor.executemany('''
                    INSERT INTO beds (hospital_id, bed_id, floor_num, floor_name, bed_type, status, patient_name, patient_age, diagnosis)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', sample_beds)
                
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Database Initialization skipped/failed: {e}")

init_db()

def get_hospital_or_404(hospital_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM hospitals WHERE id = %s', (hospital_id,))
    h = cur.fetchone()
    cur.close()
    conn.close()
    if not h:
        abort(404, description="Hospital not found.")
    return dict(h)

@app.route('/')
def home():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM hospitals')
    hospitals = cur.fetchall()
    
    h_list = []
    for h in hospitals:
        h_dict = dict(h)
        cur.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'Available' THEN 1 ELSE 0 END) as avail,
                SUM(CASE WHEN status = 'Occupied' THEN 1 ELSE 0 END) as occ
            FROM beds WHERE hospital_id = %s
        ''', (h['id'],))
        stats = cur.fetchone()
        
        h_dict['total_beds'] = stats['total'] or 0
        h_dict['avail_beds'] = stats['avail'] or 0
        h_dict['occ_beds'] = stats['occ'] or 0
        h_list.append(h_dict)
        
    cur.close()
    conn.close()
    return render_template('index.html', hospitals=h_list)

@app.route('/hospital/<hospital_id>/login', methods=['GET', 'POST'])
def hospital_login(hospital_id):
    if session.get('logged_in') and session.get('hospital_id') == hospital_id:
        return redirect(url_for('hospital_nursing', hospital_id=hospital_id))

    hospital = get_hospital_or_404(hospital_id)
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute('SELECT * FROM staff WHERE hospital_id = %s AND username = %s', (hospital_id, username))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            if user['status'] == 'pending':
                flash('Your account is currently pending verification by hospital administration.', 'error')
                return render_template('login.html', hospital=hospital, show_otp=False, show_reset_otp=False)
            elif user['status'] == 'revoked':
                flash('Your account access has been suspended. Please contact the administrator.', 'error')
                return render_template('login.html', hospital=hospital, show_otp=False, show_reset_otp=False)
                
            session['logged_in'] = True
            session['hospital_id'] = hospital_id
            session['username'] = username
            return redirect(url_for('hospital_nursing', hospital_id=hospital_id))
        else:
            flash('Invalid credentials. Please try again.', 'error')
            
    return render_template('login.html', hospital=hospital, show_otp=False, show_reset_otp=False)

@app.route('/hospital/<hospital_id>/register', methods=['POST'])
def hospital_register(hospital_id):
    hospital = get_hospital_or_404(hospital_id)
    name = request.form.get('name')
    email = request.form.get('email')
    staff_id = request.form.get('staff_id') 
    username = request.form.get('username')
    password = request.form.get('password')
    
    session['reg_data'] = {
        'hospital_id': hospital_id,
        'name': name,
        'email': email,
        'staff_id': staff_id,
        'username': username,
        'password': generate_password_hash(password)
    }
    
    otp = str(random.randint(100000, 999999))
    session['otp'] = otp
    
    email_body = f"Hello {name},\n\nYour OTP for registering a staff account at {hospital_id} is: {otp}\n\nNote: After verification, your account will require administrative approval before you can log in."
    send_system_email(email, "Verification OTP - Hospital Mainframe", email_body)
    
    flash('An OTP has been sent to your email address.', 'success')
    return render_template('login.html', hospital=hospital, show_otp=True, show_reset_otp=False)

@app.route('/hospital/<hospital_id>/verify_otp', methods=['POST'])
def verify_otp(hospital_id):
    user_otp = request.form.get('otp_code')
    
    if 'otp' in session and user_otp == session['otp']:
        reg_data = session['reg_data']
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute('''
                INSERT INTO staff (hospital_id, username, password, name, email, staff_id, status, assigned_floors)
                VALUES (%s, %s, %s, %s, %s, %s, 'pending', '[]')
            ''', (reg_data['hospital_id'], reg_data['username'], reg_data['password'], reg_data['name'], reg_data['email'], reg_data['staff_id']))
            conn.commit()
            flash('Email verified! Your account is now PENDING administrative approval.', 'success')
        except psycopg2.IntegrityError:
            flash(f'Username "{reg_data["username"]}" is already registered.', 'error')
        finally:
            cur.close()
            conn.close()
            
        session.pop('otp', None)
        session.pop('reg_data', None)
        
        hospital = get_hospital_or_404(hospital_id)
        return render_template('login.html', hospital=hospital, show_otp=False, show_reset_otp=False)
    else:
        flash('Invalid OTP Code. Please try again.', 'error')
        hospital = get_hospital_or_404(hospital_id)
        return render_template('login.html', hospital=hospital, show_otp=True, show_reset_otp=False)

@app.route('/hospital/<hospital_id>/admin/login', methods=['GET', 'POST'])
def admin_login(hospital_id):
    if session.get('admin_logged_in') and session.get('admin_hospital_id') == hospital_id:
        return redirect(url_for('hospital_admin', hospital_id=hospital_id))

    hospital = get_hospital_or_404(hospital_id)
    
    if request.method == 'POST':
        admin_id = request.form.get('admin_id')
        password = request.form.get('password')
        captcha_id = request.form.get('captcha_id')
        captcha_input = request.form.get('captcha', '').strip()
        
        session_key = f'captcha_ans_{captcha_id}'
        stored_captcha = session.get(session_key)
        
        if not captcha_input or not stored_captcha or captcha_input != stored_captcha:
            flash('Incorrect Security CAPTCHA. Please try again.', 'error')
            return redirect(url_for('admin_login', hospital_id=hospital_id))
            
        if admin_id == 'admin' and password == 'admin123':
            session['admin_logged_in'] = True
            session['admin_hospital_id'] = hospital_id
            session.pop(session_key, None) 
            return redirect(url_for('hospital_admin', hospital_id=hospital_id))
        else:
            flash('Access Denied: Invalid Admin ID or Password.', 'error')
            return redirect(url_for('admin_login', hospital_id=hospital_id))

    num1 = random.randint(1, 9)
    num2 = random.randint(1, 9)
    captcha_id = str(uuid.uuid4())
    session[f'captcha_ans_{captcha_id}'] = str(num1 + num2)
    captcha_text = f"{num1} + {num2} = ?"
    return render_template('admin_login.html', hospital=hospital, captcha_text=captcha_text, captcha_id=captcha_id)

@app.route('/hospital/<hospital_id>/admin/logout')
def admin_logout(hospital_id):
    session.pop('admin_logged_in', None)
    session.pop('admin_hospital_id', None)
    flash('Admin securely logged out.', 'success')
    return redirect(url_for('admin_login', hospital_id=hospital_id))

@app.route('/hospital/<hospital_id>/admin')
def hospital_admin(hospital_id):
    if not session.get('admin_logged_in') or session.get('admin_hospital_id') != hospital_id:
        flash('Restricted Area: Please log in with Administrative credentials.', 'error')
        return redirect(url_for('admin_login', hospital_id=hospital_id))
        
    hospital = get_hospital_or_404(hospital_id)
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    cur.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'Available' THEN 1 ELSE 0 END) as avail,
            SUM(CASE WHEN status = 'Occupied' THEN 1 ELSE 0 END) as occ
        FROM beds WHERE hospital_id = %s
    ''', (hospital_id,))
    stats = cur.fetchone()
    
    cur.execute("SELECT * FROM staff WHERE hospital_id = %s AND status = 'pending'", (hospital_id,))
    pending_staff = cur.fetchall()
    
    cur.execute("SELECT * FROM staff WHERE hospital_id = %s AND status = 'approved'", (hospital_id,))
    active_staff_raw = cur.fetchall()
    active_staff = []
    for staff in active_staff_raw:
        s_dict = dict(staff)
        s_dict['assigned_floors'] = json.loads(s_dict['assigned_floors']) if s_dict['assigned_floors'] else []
        active_staff.append(s_dict)
        
    cur.execute("SELECT * FROM staff WHERE hospital_id = %s AND status = 'revoked'", (hospital_id,))
    revoked_staff = [dict(s) for s in cur.fetchall()]
        
    cur.execute("SELECT DISTINCT floor_num, floor_name FROM beds WHERE hospital_id = %s", (hospital_id,))
    all_floors = [{'floor': str(b['floor_num']), 'name': b['floor_name']} for b in cur.fetchall()]
    
    cur.close()
    conn.close()
    
    return render_template('admin.html', hospital=hospital, stats=stats, pending_staff=pending_staff, active_staff=active_staff, revoked_staff=revoked_staff, all_floors=all_floors)

@app.route('/hospital/<hospital_id>/admin/staff/<username>/<action>', methods=['POST'])
def manage_staff(hospital_id, username, action):
    if not session.get('admin_logged_in') or session.get('admin_hospital_id') != hospital_id:
        abort(403)
        
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM staff WHERE hospital_id = %s AND username = %s", (hospital_id, username))
    user = cur.fetchone()
    
    if user:
        if action == 'approve':
            cur.execute("UPDATE staff SET status = 'approved' WHERE hospital_id = %s AND username = %s", (hospital_id, username))
            send_system_email(user['email'], "Account Approved - CARE Network", f"Hello {user['name']},\n\nYour staff account (ID: {user['staff_id']}) has been APPROVED by administration. You may now log in to the portal.")
            flash(f"Staff member {user['name']} has been approved.", "success")
            
        elif action == 'reject':
            cur.execute("DELETE FROM staff WHERE hospital_id = %s AND username = %s", (hospital_id, username))
            if user['status'] == 'pending':
                send_system_email(user['email'], "Account Rejected - CARE Network", f"Hello {user['name']},\n\nYour staff account registration was REJECTED by administration. Please contact your supervisor for details.")
            flash(f"Staff registration for {user['name']} was permanently removed.", "error")
            
        elif action == 'revoke':
            cur.execute("UPDATE staff SET status = 'revoked' WHERE hospital_id = %s AND username = %s", (hospital_id, username))
            revoke_msg = f"Hello {user['name']},\n\nYour staff account (ID: {user['staff_id']}) has been SUSPENDED by administration."
            send_system_email(user['email'], "Account Suspended - CARE Network", revoke_msg)
            flash(f"Staff account for {user['name']} has been suspended.", "success")
            
        elif action == 'restore':
            cur.execute("UPDATE staff SET status = 'approved' WHERE hospital_id = %s AND username = %s", (hospital_id, username))
            restore_msg = f"Hello {user['name']},\n\nYour staff account (ID: {user['staff_id']}) has been RESTORED by administration."
            send_system_email(user['email'], "Account Restored - CARE Network", restore_msg)
            flash(f"Staff account for {user['name']} has been restored.", "success")
            
        elif action == 'assign_floors':
            selected_floors = request.form.getlist('assigned_floors')
            cur.execute("UPDATE staff SET assigned_floors = %s WHERE hospital_id = %s AND username = %s", 
                         (json.dumps(selected_floors), hospital_id, username))
            flash(f"Updated floor permissions for {user['name']}.", "success")
            
        conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('hospital_admin', hospital_id=hospital_id))

@app.route('/hospital/<hospital_id>/forgot_password_request', methods=['POST'])
def hospital_forgot_password_request(hospital_id):
    get_hospital_or_404(hospital_id)
    username = request.form.get('username')
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM staff WHERE hospital_id = %s AND username = %s', (hospital_id, username))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if user and user['email']:
        otp = str(random.randint(100000, 999999))
        session['reset_otp'] = otp
        session['reset_username'] = username
        
        email_body = f"Hello {user['name']},\n\nYour OTP for resetting your password at {hospital_id} is: {otp}\n\nIf you did not request this, please ignore this email and contact administration."
        send_system_email(user['email'], "Password Reset OTP - Hospital Mainframe", email_body)
        
        flash('An OTP has been sent to the email registered with this username.', 'success')
        hospital = get_hospital_or_404(hospital_id)
        return render_template('login.html', hospital=hospital, show_otp=False, show_reset_otp=True)
    else:
        flash(f'No account found with username "{username}" or no email registered.', 'error')
        return redirect(url_for('hospital_login', hospital_id=hospital_id))

@app.route('/hospital/<hospital_id>/forgot_password_verify', methods=['POST'])
def hospital_forgot_password_verify(hospital_id):
    user_otp = request.form.get('otp_code')
    new_password = request.form.get('new_password')
    
    if 'reset_otp' in session and user_otp == session['reset_otp']:
        username = session.get('reset_username')
        hashed_pw = generate_password_hash(new_password)
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('UPDATE staff SET password = %s WHERE hospital_id = %s AND username = %s', (hashed_pw, hospital_id, username))
        conn.commit()
        cur.close()
        conn.close()
        
        session.pop('reset_otp', None)
        session.pop('reset_username', None)
        
        flash('Password updated successfully! You can now log in with your new password.', 'success')
        return redirect(url_for('hospital_login', hospital_id=hospital_id))
    else:
        flash('Invalid OTP Code. Please request a new one or try again.', 'error')
        hospital = get_hospital_or_404(hospital_id)
        return render_template('login.html', hospital=hospital, show_otp=False, show_reset_otp=True)

@app.route('/logout')
def logout():
    h_id = session.get('hospital_id')
    session.clear()
    if h_id:
        return redirect(url_for('hospital_login', hospital_id=h_id))
    return redirect(url_for('home'))

@app.route('/hospital/<hospital_id>/nursing')
def hospital_nursing(hospital_id):
    hospital = get_hospital_or_404(hospital_id)
    
    if not session.get('logged_in') or session.get('hospital_id') != hospital_id:
        flash("You must authenticate with staff credentials for this facility.", "error")
        return redirect(url_for('hospital_login', hospital_id=hospital_id))
        
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT status FROM staff WHERE hospital_id = %s AND username = %s", (hospital_id, session.get('username')))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if not user or user['status'] != 'approved':
        session.clear()
        flash("Your account access has been suspended. Please contact the administrator.", "error")
        return redirect(url_for('hospital_login', hospital_id=hospital_id))
        
    return render_template('nursing.html', hospital=hospital, username=session.get('username'))

@app.route('/hospital/<hospital_id>/counter')
def hospital_counter(hospital_id):
    hospital = get_hospital_or_404(hospital_id)
    return render_template('counter.html', hospital=hospital)

@app.route('/api/<hospital_id>/beds')
def get_hospital_beds(hospital_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM beds WHERE hospital_id = %s ORDER BY floor_num, bed_id', (hospital_id,))
    beds = cur.fetchall()
    
    is_staff = session.get('logged_in') and session.get('hospital_id') == hospital_id
    username = session.get('username')
    allowed_floors = None
    
    if is_staff:
        cur.execute('SELECT status, assigned_floors FROM staff WHERE hospital_id = %s AND username = %s', (hospital_id, username))
        user = cur.fetchone()
        if user and user['status'] == 'approved' and user['assigned_floors']:
            allowed_floors = json.loads(user['assigned_floors'])
        else:
            allowed_floors = [] 

    cur.close()
    conn.close()
    
    hospital_data = {}
    for row in beds:
        floor_num = str(row['floor_num'])
        if allowed_floors is not None and floor_num not in allowed_floors:
            continue
            
        if floor_num not in hospital_data:
            hospital_data[floor_num] = {"floor": floor_num, "name": row['floor_name'], "beds": []}
            
        hospital_data[floor_num]["beds"].append({
            "id": row['bed_id'],
            "type": row['bed_type'],
            "status": row['status'],
            "patient_name": row['patient_name'],
            "patient_age": row['patient_age'],
            "diagnosis": row['diagnosis']
        })
        
    return jsonify(list(hospital_data.values()))

@app.route('/api/<hospital_id>/add_bed', methods=['POST'])
def add_hospital_bed(hospital_id):
    if not session.get('logged_in') or session.get('hospital_id') != hospital_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
        
    username = session.get('username')
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    cur.execute("SELECT status FROM staff WHERE hospital_id = %s AND username = %s", (hospital_id, username))
    user = cur.fetchone()
    if not user or user['status'] != 'approved':
        cur.close()
        conn.close()
        return jsonify({"success": False, "error": "Account suspended"}), 403
        
    data = request.json
    floor_num = str(data['floor_num'])
    
    try:
        cur.execute('''
            INSERT INTO beds (hospital_id, bed_id, floor_num, floor_name, bed_type, status, patient_name, patient_age, diagnosis)
            VALUES (%s, %s, %s, %s, %s, 'Available', '', '', '')
        ''', (hospital_id, data['bed_id'], floor_num, data['floor_name'], data['bed_type']))
        
        cur.execute('SELECT assigned_floors FROM staff WHERE hospital_id = %s AND username = %s', (hospital_id, username))
        user_db = cur.fetchone()
        if user_db:
            user_floors = json.loads(user_db['assigned_floors']) if user_db['assigned_floors'] else []
            if floor_num not in user_floors:
                user_floors.append(floor_num)
                cur.execute('UPDATE staff SET assigned_floors = %s WHERE hospital_id = %s AND username = %s', 
                             (json.dumps(user_floors), hospital_id, username))
        
        conn.commit()
        success = True
    except psycopg2.IntegrityError:
        success = False
    finally:
        cur.close()
        conn.close()
    
    if success:
        socketio.emit('system_refresh', {'hospital_id': hospital_id}, room=hospital_id)
        socketio.emit('global_network_refresh')
    return jsonify({"success": success})

@app.route('/api/<hospital_id>/delete_bed', methods=['POST'])
def delete_hospital_bed(hospital_id):
    if not session.get('logged_in') or session.get('hospital_id') != hospital_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
        
    username = session.get('username')
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    cur.execute("SELECT status FROM staff WHERE hospital_id = %s AND username = %s", (hospital_id, username))
    user = cur.fetchone()
    if not user or user['status'] != 'approved':
        cur.close()
        conn.close()
        return jsonify({"success": False, "error": "Account suspended"}), 403
        
    data = request.json
    try:
        cur.execute('DELETE FROM beds WHERE hospital_id = %s AND bed_id = %s', (hospital_id, data['bed_id']))
        conn.commit()
        success = True
    except Exception as e:
        success = False
    finally:
        cur.close()
        conn.close()
    
    if success:
        socketio.emit('system_refresh', {'hospital_id': hospital_id}, room=hospital_id)
        socketio.emit('global_network_refresh')
    return jsonify({"success": success})

@app.route('/api/chat', methods=['POST'])
def chat_bot():
    data = request.json
    user_message = data.get('message', '').lower()
    
    response = "I am the CARE Network AI running on the backend server. How can I assist you today?"
    
    if 'bed' in user_message or 'available' in user_message:
        response = "You can view real-time bed availability for all hospitals directly on the dashboard cards. Green indicates available beds."
    elif 'location' in user_message or 'near' in user_message:
        response = "The dashboard automatically requested your location when you opened the page to sort the nearest hospitals to the top."
    elif 'review' in user_message or 'rating' in user_message:
        response = "Hospital ratings are visible in the top left corner of their images. Manipal and Sahyadri are currently rated the highest."
    elif 'add' in user_message or 'staff' in user_message:
        response = "To manage hospital infrastructure, please click the 'Staff Portal' button for the respective hospital and log in with your credentials."
        
    return jsonify({"response": response})

# --- WEBSOCKETS (ROOM ISOLATION) ---

@socketio.on('join_hospital')
def on_join(data):
    hospital_id = data.get('hospital_id')
    if hospital_id:
        join_room(hospital_id)

@socketio.on('update_bed_status')
def handle_bed_update(data):
    hospital_id = data.get('hospital_id')
    
    if not session.get('logged_in') or session.get('hospital_id') != hospital_id:
        return 
        
    username = session.get('username')
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT status FROM staff WHERE hospital_id = %s AND username = %s", (hospital_id, username))
    user = cur.fetchone()
    
    if not user or user['status'] != 'approved':
        cur.close()
        conn.close()
        return 
        
    bed_id = data.get('bed_id')
    new_status = data.get('status')
    
    if new_status in ['Occupied', 'Discharge Hold']:
        p_name = data.get('patient_name', '')
        p_age = data.get('patient_age', '')
        p_diag = data.get('diagnosis', '')
    else:
        p_name, p_age, p_diag = "", "", ""
        
    cur.execute('''
        UPDATE beds 
        SET status = %s, patient_name = %s, patient_age = %s, diagnosis = %s 
        WHERE hospital_id = %s AND bed_id = %s
    ''', (new_status, p_name, p_age, p_diag, hospital_id, bed_id))
    conn.commit()
    cur.close()
    conn.close()
    
    emit('bed_updated', data, room=hospital_id)
    emit('global_network_refresh', broadcast=True)

if __name__ == '__main__':
    socketio.run(app, port=8080, debug=True, allow_unsafe_werkzeug=True)
