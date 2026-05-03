# database.py - Complete database with security features and patient anonymization
import sqlite3
from datetime import datetime, timedelta
import bcrypt

class Database:
    def __init__(self, db_path="afyahiv_care.db"):
        self.db_path = db_path
        self.init_tables()
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def init_tables(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Patients table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                phone_number TEXT NOT NULL,
                language TEXT DEFAULT 'English',
                location TEXT,
                arv_regimen TEXT,
                medication_time TEXT,
                registration_date TEXT,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        # Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL,
                direction TEXT CHECK(direction IN ('incoming', 'outgoing')),
                type TEXT CHECK(type IN ('sms', 'voice')),
                content TEXT NOT NULL,
                language TEXT,
                risk_level TEXT DEFAULT 'low',
                symptoms_detected TEXT,
                response_sent TEXT,
                timestamp TEXT,
                is_read INTEGER DEFAULT 0,
                is_emergency INTEGER DEFAULT 0
            )
        ''')
        
        # Providers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                full_name TEXT,
                role TEXT DEFAULT 'doctor',
                hospital TEXT,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Adherence table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS adherence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL,
                date TEXT NOT NULL,
                dose_taken INTEGER DEFAULT 0,
                reminder_sent INTEGER DEFAULT 0,
                notes TEXT
            )
        ''')
        
        # Villages table for GIS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS villages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL
            )
        ''')
        
        # Hospitals table for GIS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hospitals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                village TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                level INTEGER,
                phone TEXT,
                address TEXT,
                opening_hours TEXT
            )
        ''')
        
        # Pre-calculated distances
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hospital_distances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                village_name TEXT NOT NULL,
                hospital_name TEXT NOT NULL,
                distance_km REAL NOT NULL,
                travel_time_minutes INTEGER NOT NULL,
                directions TEXT
            )
        ''')
        
        # ============================================================
        # SECURITY TABLES
        # ============================================================
        
        # Failed logins table for lockout
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS failed_logins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                phone_number TEXT,
                attempt_time TEXT NOT NULL,
                ip_address TEXT
            )
        ''')
        
        # Audit logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_type TEXT NOT NULL,
                user_id TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                ip_address TEXT,
                timestamp TEXT NOT NULL
            )
        ''')
        
        # ============================================================
        # INSERT SAMPLE DATA
        # ============================================================
        
        # Insert villages
        cursor.execute("SELECT COUNT(*) FROM villages")
        if cursor.fetchone()[0] == 0:
            villages = [
                ("Siaya Town", -0.0614, 34.2880),
                ("Bondo", -0.0980, 34.2730),
                ("Kisumu", -0.1035, 34.7550),
                ("Rangala", 0.0720, 34.1580),
                ("Ugunja", 0.1650, 34.1200)
            ]
            cursor.executemany("INSERT INTO villages (name, latitude, longitude) VALUES (?, ?, ?)", villages)
        
        # Insert hospitals
        cursor.execute("SELECT COUNT(*) FROM hospitals")
        if cursor.fetchone()[0] == 0:
            hospitals = [
                ("Siaya County Referral Hospital", "Siaya Town", -0.0614, 34.2880, 5, "057-123456", "Siaya Town, along Kisumu Road", "24/7"),
                ("Bondo Sub-County Hospital", "Bondo", -0.0980, 34.2730, 4, "057-345678", "Bondo Town, near Police Station", "24/7"),
                ("Jaramogi Oginga Odinga Hospital", "Kisumu", -0.1035, 34.7550, 5, "057-456789", "Kisumu City, along Jomo Kenyatta Highway", "24/7"),
                ("Rangala Health Centre", "Rangala", 0.0720, 34.1580, 3, "057-567890", "Rangala Market, Siaya County", "8am-5pm"),
                ("Ugunja Sub-County Hospital", "Ugunja", 0.1650, 34.1200, 4, "057-678901", "Ugunja Town", "24/7")
            ]
            cursor.executemany("INSERT INTO hospitals (name, village, latitude, longitude, level, phone, address, opening_hours) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", hospitals)
        
        # Insert distances
        cursor.execute("SELECT COUNT(*) FROM hospital_distances")
        if cursor.fetchone()[0] == 0:
            distances = [
                ("Siaya Town", "Siaya County Referral Hospital", 2.0, 5, "Head towards the main road. The hospital is 2km ahead on your left."),
                ("Bondo", "Bondo Sub-County Hospital", 1.5, 4, "Walk towards the town center. Hospital is near the police station."),
                ("Kisumu", "Jaramogi Oginga Odinga Hospital", 3.0, 8, "Head towards the city center. Hospital is along Jomo Kenyatta Highway."),
                ("Rangala", "Rangala Health Centre", 1.0, 3, "Walk towards the market. Health centre is on the main road."),
                ("Ugunja", "Ugunja Sub-County Hospital", 2.5, 6, "Head towards Ugunja Town center. Hospital is near the bus stage.")
            ]
            cursor.executemany("INSERT INTO hospital_distances (village_name, hospital_name, distance_km, travel_time_minutes, directions) VALUES (?, ?, ?, ?, ?)", distances)
        
        # Insert doctor with bcrypt hashed password
        cursor.execute("SELECT COUNT(*) FROM providers")
        if cursor.fetchone()[0] == 0:
            hashed_password = bcrypt.hashpw("doctor123".encode(), bcrypt.gensalt()).decode('utf-8')
            cursor.execute("INSERT INTO providers (username, password, full_name, role, hospital) VALUES (?, ?, ?, ?, ?)",
                         ("dr.mwangi", hashed_password, "Dr. James Mwangi", "doctor", "Siaya County Hospital"))
        
        # Insert sample patients
        cursor.execute("SELECT COUNT(*) FROM patients")
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO patients (patient_id, full_name, phone_number, language, location, arv_regimen, medication_time, registration_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', ("HIV001", "Mary Atieno", "+254712345678", "Kiswahili", "Siaya Town", "TLD", "20:00", datetime.now().isoformat()))
            
            cursor.execute('''
                INSERT INTO patients (patient_id, full_name, phone_number, language, location, arv_regimen, medication_time, registration_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', ("HIV002", "John Omondi", "+254723456789", "English", "Bondo", "TLD", "20:00", datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    # ============================================================
    # SECURITY METHODS
    # ============================================================
    
    def record_failed_login(self, username=None, phone_number=None, ip_address=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO failed_logins (username, phone_number, attempt_time, ip_address)
            VALUES (?, ?, ?, ?)
        ''', (username, phone_number, datetime.now().isoformat(), ip_address))
        conn.commit()
        conn.close()

    def get_failed_attempts(self, username=None, phone_number=None, minutes=15):
        conn = self.get_connection()
        cursor = conn.cursor()
        time_threshold = (datetime.now() - timedelta(minutes=minutes)).isoformat()
        
        if username:
            cursor.execute('''
                SELECT COUNT(*) FROM failed_logins 
                WHERE username = ? AND attempt_time > ?
            ''', (username, time_threshold))
        elif phone_number:
            cursor.execute('''
                SELECT COUNT(*) FROM failed_logins 
                WHERE phone_number = ? AND attempt_time > ?
            ''', (phone_number, time_threshold))
        else:
            conn.close()
            return 0
        
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def clear_failed_attempts(self, username=None, phone_number=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        if username:
            cursor.execute("DELETE FROM failed_logins WHERE username = ?", (username,))
        elif phone_number:
            cursor.execute("DELETE FROM failed_logins WHERE phone_number = ?", (phone_number,))
        conn.commit()
        conn.close()
    
    def add_audit_log(self, user_type, user_id, action, details=None, ip_address=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO audit_logs (user_type, user_id, action, details, ip_address, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_type, user_id, action, details, ip_address, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    
    # ============================================================
    # PATIENT METHODS
    # ============================================================
    
    def get_all_patients(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM patients WHERE status = 'active'")
        patients = cursor.fetchall()
        conn.close()
        return patients
    
    def get_all_patients_anonymized(self):
        """Get patients with ID only - NO NAMES (for doctor dashboard)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT patient_id, phone_number, language, location, arv_regimen, medication_time, status FROM patients WHERE status = 'active'")
        patients = cursor.fetchall()
        conn.close()
        
        result = []
        for p in patients:
            result.append({
                'id': p[0],
                'phone_last4': p[1][-4:] if p[1] and len(p[1]) >= 4 else '****',
                'language': p[2],
                'location': p[3],
                'arv_regimen': p[4],
                'medication_time': p[5]
            })
        return result
    
    def get_patient_by_id(self, patient_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
        patient = cursor.fetchone()
        conn.close()
        return patient
    
    def get_patient_by_phone(self, phone_number):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM patients WHERE phone_number = ?", (phone_number,))
        patient = cursor.fetchone()
        conn.close()
        return patient
    
    def register_patient(self, patient_data):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO patients (patient_id, full_name, phone_number, language, location, arv_regimen, medication_time, registration_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', patient_data)
        conn.commit()
        conn.close()
    
    # ============================================================
    # MESSAGE METHODS
    # ============================================================
    
    def save_message(self, patient_id, direction, msg_type, content, language, risk_level, symptoms, response):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO messages (patient_id, direction, type, content, language, risk_level, symptoms_detected, response_sent, timestamp, is_emergency)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (patient_id, direction, msg_type, content, language, risk_level, symptoms, response, datetime.now().isoformat(), 1 if risk_level == 'high' else 0))
        conn.commit()
        conn.close()
    
    def get_patient_messages(self, patient_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, patient_id, direction, type, content, language, risk_level, symptoms_detected, response_sent, timestamp, is_read, is_emergency FROM messages WHERE patient_id = ? ORDER BY timestamp DESC LIMIT 50", (patient_id,))
        messages = cursor.fetchall()
        conn.close()
        return messages
    
    def get_unread_messages(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT m.id, m.patient_id, m.direction, m.type, m.content, m.language, m.risk_level, m.symptoms_detected, m.response_sent, m.timestamp, m.is_read, m.is_emergency, p.full_name, p.phone_number
            FROM messages m 
            JOIN patients p ON m.patient_id = p.patient_id 
            WHERE m.direction = 'incoming' AND m.is_read = 0 
            ORDER BY m.timestamp DESC
        ''')
        messages = cursor.fetchall()
        conn.close()
        return messages
    
    def get_all_messages_for_doctor(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT m.id, m.patient_id, m.direction, m.type, m.content, m.language, m.risk_level, m.symptoms_detected, m.response_sent, m.timestamp, m.is_read, m.is_emergency, p.full_name, p.phone_number, p.location
            FROM messages m 
            JOIN patients p ON m.patient_id = p.patient_id 
            WHERE m.direction = 'incoming'
            ORDER BY m.timestamp DESC
            LIMIT 50
        ''')
        messages = cursor.fetchall()
        conn.close()
        return messages
    
    def mark_message_read(self, message_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE messages SET is_read = 1 WHERE id = ?", (message_id,))
        conn.commit()
        conn.close()
    
    # ============================================================
    # PROVIDER METHODS
    # ============================================================
    
    def authenticate_provider(self, username, password):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM providers WHERE username = ? AND is_active = 1", (username,))
        provider = cursor.fetchone()
        conn.close()
        
        if provider:
            stored_password = provider[2]
            if bcrypt.checkpw(password.encode(), stored_password.encode()):
                return provider
        return None
    
    def send_message_to_patient(self, patient_id, message, provider_name):
        conn = self.get_connection()
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO messages (patient_id, direction, type, content, language, risk_level, response_sent, timestamp)
            VALUES (?, 'outgoing', 'sms', ?, 'English', 'none', ?, ?)
        ''', (patient_id, message, f"Sent by {provider_name}", timestamp))
        conn.commit()
        conn.close()
        return True
    
    def get_emergency_alerts(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT m.id, m.patient_id, m.direction, m.type, m.content, m.language, m.risk_level, m.symptoms_detected, m.response_sent, m.timestamp, m.is_read, m.is_emergency, p.full_name, p.phone_number, p.location
            FROM messages m 
            JOIN patients p ON m.patient_id = p.patient_id 
            WHERE m.is_emergency = 1 AND m.direction = 'incoming'
            ORDER BY m.timestamp DESC
        ''')
        alerts = cursor.fetchall()
        conn.close()
        return alerts
    
    # ============================================================
    # ADHERENCE METHODS
    # ============================================================
    
    def get_adherence_stats(self, patient_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM adherence WHERE patient_id = ? AND dose_taken = 1", (patient_id,))
        taken = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM adherence WHERE patient_id = ?", (patient_id,))
        total = cursor.fetchone()[0]
        conn.close()
        return (taken, total) if total > 0 else (0, 0)
    
    def add_adherence_record(self, patient_id, dose_taken=1):
        conn = self.get_connection()
        cursor = conn.cursor()
        today = datetime.now().date().isoformat()
        cursor.execute("SELECT * FROM adherence WHERE patient_id = ? AND date = ?", (patient_id, today))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO adherence (patient_id, date, dose_taken) VALUES (?, ?, ?)", 
                         (patient_id, today, dose_taken))
            conn.commit()
        conn.close()
    
    # ============================================================
    # GIS METHODS
    # ============================================================
    
    def get_all_villages(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM villages ORDER BY name")
        villages = cursor.fetchall()
        conn.close()
        return [v[0] for v in villages]
    
    def get_nearest_hospital(self, village_name):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT h.name, h.village, h.level, h.phone, h.address, h.opening_hours,
                   hd.distance_km, hd.travel_time_minutes, hd.directions
            FROM hospital_distances hd
            JOIN hospitals h ON h.name = hd.hospital_name
            WHERE hd.village_name = ?
            LIMIT 1
        ''', (village_name,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'name': result[0],
                'village': result[1],
                'level': result[2],
                'phone': result[3],
                'address': result[4],
                'opening_hours': result[5],
                'distance_km': result[6],
                'travel_time_minutes': result[7],
                'directions': result[8]
            }
        return None
    
    def update_patient_location(self, patient_id, new_location):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE patients SET location = ? WHERE patient_id = ?", (new_location, patient_id))
        conn.commit()
        conn.close()