# app.py - Complete AFYAHIV CARE with Patient Anonymization
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from database import Database
from ai_engine import AIEngine
from sms_handler import SMSHandler, AfricaTalkingSandbox
from voice_simulator import VoiceSimulator
from datetime import datetime, timedelta
from functools import wraps
import uuid
import re

app = Flask(__name__)
app.secret_key = "afyahiv-care-secret-key-2024"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=15)

# Initialize components
db = Database()
ai_engine = AIEngine()
sms_handler = SMSHandler(ai_engine, db)
voice_simulator = VoiceSimulator(ai_engine, sms_handler, db)

# ============================================================
# HELPER FUNCTION
# ============================================================

def format_phone(phone):
    """Convert any phone input to +254XXXXXXXXX format"""
    phone = re.sub(r'\D', '', str(phone))
    if phone.startswith('0'):
        phone = phone[1:]
    elif phone.startswith('254'):
        phone = phone[3:]
    return f"+254{phone}"

# Session required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_type' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================================
# PATIENT DASHBOARD ROUTES
# ============================================================

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/patient/login', methods=['POST'])
def patient_login():
    phone = request.form.get('phone')
    patient_id = request.form.get('patient_id')
    
    # Check failed attempts
    failed_count = db.get_failed_attempts(phone_number=phone)
    if failed_count >= 5:
        return render_template('login.html', error="Account locked. Too many failed attempts. Try again later.")
    
    patient = db.get_patient_by_id(patient_id)
    if patient and patient[3] == phone:
        db.clear_failed_attempts(phone_number=phone)
        session['user_type'] = 'patient'
        session['patient_id'] = patient_id
        # Do NOT store patient name in session - anonymous
        session['patient_phone'] = patient[3]
        session['patient_language'] = patient[4]
        session['patient_location'] = patient[5]
        session.permanent = True
        # Audit log (name not stored in log)
        db.add_audit_log('patient', patient_id, 'login', f'Patient {patient_id} logged in')
        return redirect(url_for('patient_dashboard'))
    
    # Record failed attempt
    db.record_failed_login(phone_number=phone)
    return render_template('login.html', error="Invalid credentials")

@app.route('/patient/dashboard')
@login_required
def patient_dashboard():
    if session.get('user_type') != 'patient':
        return redirect(url_for('index'))
    
    patient_id = session['patient_id']
    patient = db.get_patient_by_id(patient_id)
    messages = db.get_patient_messages(patient_id)
    taken, total = db.get_adherence_stats(patient_id)
    adherence_percent = (taken / total * 100) if total > 0 else 85
    
    # Safe unread count
    unread = 0
    for m in messages:
        try:
            if len(m) > 13 and m[13] == 0:
                unread += 1
        except (IndexError, TypeError):
            pass
    
    # Get all villages for dropdown
    villages = db.get_all_villages()
    
    # Pass only patient_id, NOT name
    return render_template('patient_dashboard.html',
                         patient_id=patient_id,
                         patient_location=patient[5] if patient else 'Unknown',
                         patient_arv=patient[6] if patient else 'TLD',
                         patient_time=patient[7] if patient else '20:00',
                         patient_language=patient[4] if patient else 'English',
                         messages=messages[:20],
                         adherence_percent=adherence_percent,
                         unread_count=unread,
                         villages=villages,
                         session=session)

@app.route('/patient/send_report', methods=['POST'])
@login_required
def patient_send_report():
    if session.get('user_type') != 'patient':
        return jsonify({"error": "Unauthorized"}), 401
    
    report_text = request.form.get('report_text')
    report_type = request.form.get('report_type', 'sms')
    
    patient_id = session['patient_id']
    patient = db.get_patient_by_id(patient_id)
    
    if not patient:
        return jsonify({"error": "Patient not found"}), 404
    
    if report_type == 'sms':
        result = sms_handler.receive_sms(patient[3], report_text)
    else:
        analysis = voice_simulator.simulate_voice_call(patient[3])
        result = {"status": "processed", "response": analysis['response']}
    
    return jsonify(result)

@app.route('/patient/messages')
@login_required
def patient_messages():
    if session.get('user_type') != 'patient':
        return jsonify({"error": "Unauthorized"}), 401
    
    patient_id = session['patient_id']
    messages = db.get_patient_messages(patient_id)
    
    message_list = []
    for msg in messages:
        try:
            message_list.append({
                'id': msg[0],
                'direction': msg[2],
                'type': msg[3],
                'content': msg[4],
                'risk_level': msg[6],
                'timestamp': msg[9]
            })
        except IndexError:
            pass
    
    return jsonify(message_list)

# ============================================================
# GIS HOSPITAL LOCATOR ROUTES
# ============================================================

@app.route('/patient/find_hospital', methods=['POST'])
@login_required
def patient_find_hospital():
    if session.get('user_type') != 'patient':
        return jsonify({"error": "Unauthorized"}), 401
    
    selected_village = request.form.get('village')
    patient_id = session['patient_id']
    
    if selected_village:
        db.update_patient_location(patient_id, selected_village)
        session['patient_location'] = selected_village
    
    hospital = db.get_nearest_hospital(selected_village)
    
    if hospital:
        return jsonify({
            'status': 'success',
            'hospital': hospital,
            'village': selected_village
        })
    else:
        return jsonify({'status': 'error', 'message': 'No hospital found for this location'})

@app.route('/patient/update_location', methods=['POST'])
@login_required
def patient_update_location():
    if session.get('user_type') != 'patient':
        return jsonify({"error": "Unauthorized"}), 401
    
    new_location = request.form.get('location')
    patient_id = session['patient_id']
    
    db.update_patient_location(patient_id, new_location)
    session['patient_location'] = new_location
    
    return jsonify({'status': 'success', 'message': f'Location updated to {new_location}'})

@app.route('/patient/update_language', methods=['POST'])
@login_required
def patient_update_language():
    if session.get('user_type') != 'patient':
        return jsonify({"error": "Unauthorized"}), 401
    
    language = request.form.get('language')
    patient_id = session['patient_id']
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE patients SET language = ? WHERE patient_id = ?", (language, patient_id))
    conn.commit()
    conn.close()
    
    session['patient_language'] = language
    
    return jsonify({"status": "success", "message": f"Language updated to {language}"})

# ============================================================
# DOCTOR DASHBOARD ROUTES (ANONYMIZED - NO PATIENT NAMES)
# ============================================================

@app.route('/doctor/login', methods=['POST'])
def doctor_login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    # Check failed attempts
    failed_count = db.get_failed_attempts(username=username)
    if failed_count >= 5:
        return render_template('login.html', error="Account locked. Too many failed attempts. Try again later.")
    
    provider = db.authenticate_provider(username, password)
    if provider:
        db.clear_failed_attempts(username=username)
        session['user_type'] = 'doctor'
        session['doctor_id'] = provider[0]
        session['doctor_name'] = provider[3]
        session['hospital'] = provider[5]
        session.permanent = True
        # Audit log
        db.add_audit_log('doctor', username, 'login', f'Doctor {provider[3]} logged in')
        return redirect(url_for('doctor_dashboard'))
    
    # Record failed attempt
    db.record_failed_login(username=username)
    return render_template('login.html', error="Invalid doctor credentials")

@app.route('/doctor/dashboard')
@login_required
def doctor_dashboard():
    if session.get('user_type') != 'doctor':
        return redirect(url_for('index'))
    
    patients = db.get_all_patients()
    unread_messages = db.get_unread_messages()
    emergency_alerts = db.get_emergency_alerts()
    all_messages = db.get_all_messages_for_doctor()
    
    # ANONYMIZED patient data - NO NAMES shown to doctor
    patient_data = []
    for patient in patients:
        taken, total = db.get_adherence_stats(patient[1])
        adherence = (taken / total * 100) if total > 0 else 85
        
        nearest_hospital = db.get_nearest_hospital(patient[5])
        
        # Only show Patient ID, NOT name
        patient_data.append({
            'id': patient[1],  # Only Patient ID visible
            'phone': patient[3][-4:],  # Only last 4 digits of phone
            'language': patient[4],
            'location': patient[5],
            'arv_regimen': patient[6],
            'medication_time': patient[7],
            'adherence': adherence,
            'nearest_hospital': nearest_hospital['name'] if nearest_hospital else 'N/A',
            'hospital_distance': nearest_hospital['distance_km'] if nearest_hospital else 'N/A'
        })
    
    villages = db.get_all_villages()
    
    return render_template('doctor_dashboard.html',
                         patients=patient_data,
                         unread_messages=unread_messages,
                         emergency_alerts=emergency_alerts,
                         all_messages=all_messages,
                         villages=villages,
                         session=session)

@app.route('/doctor/send_message', methods=['POST'])
@login_required
def doctor_send_message():
    if session.get('user_type') != 'doctor':
        return jsonify({"error": "Unauthorized"}), 401
    
    patient_id = request.form.get('patient_id')
    message = request.form.get('message')
    
    patient = db.get_patient_by_id(patient_id)
    if not patient:
        return jsonify({"error": "Patient not found"}), 404
    
    # Send message using patient_id (name never shown)
    sms_handler.send_sms(patient[3], message, patient[4])
    db.send_message_to_patient(patient_id, message, session['doctor_name'])
    
    return jsonify({"status": "success", "message": f"Message sent to Patient {patient_id}"})

@app.route('/doctor/register_patient', methods=['POST'])
@login_required
def doctor_register_patient():
    if session.get('user_type') != 'doctor':
        return jsonify({"error": "Unauthorized"}), 401
    
    patient_id = f"HIV{str(uuid.uuid4())[:5].upper()}"
    phone = format_phone(request.form.get('phone_number'))
    full_name = request.form.get('full_name')  # Stored but NEVER displayed
    
    db.register_patient((
        patient_id,
        full_name,
        phone,
        request.form.get('language', 'English'),
        request.form.get('location'),
        request.form.get('arv_regimen', 'TLD'),
        request.form.get('medication_time', '20:00'),
        datetime.now().isoformat()
    ))
    
    welcome_msg = f"WELCOME! Your Patient ID: {patient_id}. Visit your dashboard to find nearest hospital."
    sms_handler.send_sms(phone, welcome_msg, request.form.get('language', 'English'))
    
    # Audit log - name stored but not displayed anywhere
    db.add_audit_log('doctor', session.get('doctor_name', ''), 'register_patient', f'Registered patient {patient_id}')
    
    return jsonify({"status": "success", "patient_id": patient_id})

@app.route('/doctor/mark_read/<int:message_id>', methods=['POST'])
@login_required
def mark_message_read(message_id):
    db.mark_message_read(message_id)
    return jsonify({"status": "success"})

@app.route('/doctor/patient/<patient_id>')
@login_required
def doctor_patient_detail(patient_id):
    if session.get('user_type') != 'doctor':
        return jsonify({"error": "Unauthorized"}), 401
    
    patient = db.get_patient_by_id(patient_id)
    if not patient:
        return jsonify({"error": "Patient not found"}), 404
    
    messages = db.get_patient_messages(patient_id)
    taken, total = db.get_adherence_stats(patient_id)
    nearest_hospital = db.get_nearest_hospital(patient[5])
    
    # Audit log for viewing patient details - name NOT logged
    db.add_audit_log('doctor', session.get('doctor_name', ''), 'view_patient', f'Viewed patient {patient_id} details')
    
    # Return data WITHOUT patient name
    return jsonify({
        'patient': {
            'id': patient[1],  # Only ID shown, NO NAME
            'phone': patient[3][-4:],  # Only last 4 digits
            'language': patient[4],
            'location': patient[5],
            'arv_regimen': patient[6],
            'medication_time': patient[7]
        },
        'adherence': {
            'taken': taken,
            'total': total,
            'percentage': (taken / total * 100) if total > 0 else 85
        },
        'nearest_hospital': nearest_hospital,
        'messages': []
    })

# ============================================================
# REGISTRATION ROUTES
# ============================================================

@app.route('/register_patient', methods=['GET', 'POST'])
def register_patient():
    if request.method == 'POST':
        patient_id = f"HIV{str(uuid.uuid4())[:5].upper()}"
        phone = format_phone(request.form.get('phone_number'))
        
        patient_data = (
            patient_id,
            request.form.get('full_name'),
            phone,
            request.form.get('language', 'English'),
            request.form.get('location'),
            request.form.get('arv_regimen', 'TLD'),
            request.form.get('medication_time', '20:00'),
            datetime.now().isoformat()
        )
        
        db.register_patient(patient_data)
        
        patient = db.get_patient_by_id(patient_id)
        if patient:
            welcome_msg = f"Welcome! Your Patient ID: {patient_id}. Your ARV reminder is set for {patient[7]} daily."
            sms_handler.send_sms(patient[3], welcome_msg, patient[4])
        
        return render_template('register.html', success=True, patient_id=patient_id)
    
    return render_template('register.html')

# ============================================================
# SIMULATION ROUTES
# ============================================================

@app.route('/simulate/sms')
@login_required
def simulate_sms():
    if session.get('user_type') != 'doctor':
        return redirect(url_for('index'))
    return render_template('sms_simulator.html', patients=db.get_all_patients_anonymized())

@app.route('/simulate/voice')
@login_required
def simulate_voice():
    if session.get('user_type') != 'doctor':
        return redirect(url_for('index'))
    AfricaTalkingSandbox.simulate_voice_flow()
    return render_template('voice_simulator.html')

@app.route('/api/process_voice', methods=['POST'])
def process_voice():
    transcribed_text = request.json.get('text', '')
    patient_phone = request.json.get('phone', None)
    
    analysis = ai_engine.analyze_text(transcribed_text)
    
    patients = db.get_all_patients()
    for p in patients:
        if patient_phone and p[3] == patient_phone:
            db.save_message(
                p[1], 'incoming', 'voice', transcribed_text, p[4],
                analysis['risk_level'], ','.join(analysis['symptoms']), analysis['response']
            )
            break
    
    return jsonify(analysis)

# ============================================================
# DEMO ROUTES
# ============================================================

@app.route('/demo/scenario2')
def demo_scenario2():
    sms_handler.receive_sms("+254723456789", "Feeling better today. No side effects.")
    return jsonify({"scenario": "Routine English SMS", "status": "completed"})

@app.route('/demo/scenario3')
def demo_scenario3():
    sms_handler.receive_sms("+254712345678", "Nina damu na maumivu makali.")
    return jsonify({"scenario": "Emergency Kiswahili SMS", "status": "completed"})

@app.route('/demo/scenario4')
def demo_scenario4():
    voice_simulator.simulate_voice_call("+254712345678")
    return jsonify({"scenario": "Voice Call Report", "status": "completed"})

@app.route('/demo/scenario6')
def demo_scenario6():
    return redirect(url_for('doctor_dashboard'))

@app.route('/logout')
def logout():
    if session.get('user_type') == 'patient':
        db.add_audit_log('patient', session.get('patient_id', ''), 'logout', 'User logged out')
    elif session.get('user_type') == 'doctor':
        db.add_audit_log('doctor', session.get('doctor_name', ''), 'logout', 'User logged out')
    session.clear()
    return redirect(url_for('index'))

# ============================================================
# MAIN ENTRY POINT
# ============================================================

if __name__ == '__main__':
    print("\n" + "="*70)
    print("AFYAHIV CARE - AI-Powered Medication Adherence System")
    print("="*70)
    print("\nSystem Initialized Successfully!")
    print("\nSECURITY FEATURE: Patient names are HIDDEN from doctors")
    print("Patients are identified ONLY by their Patient ID (e.g., HIV001)")
    print("\nDemo Accounts:")
    print("   Doctor: dr.mwangi / doctor123")
    print("   Patient 1: HIV001 / Phone: +254712345678")
    print("   Patient 2: HIV002 / Phone: +254723456789")
    print("\nAccess the application at: http://localhost:5000")
    print("\nStarting server...")
    print("="*70 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)