# sms_handler.py - SMS handling for AFYAHIV CARE
class SMSHandler:
    def __init__(self, ai_engine, database):
        self.ai_engine = ai_engine
        self.db = database
    
    def send_sms(self, phone_number, message, language='English'):
        print(f"\nSMS SENT to {phone_number}: {message}\n")
        
        patients = self.db.get_all_patients()
        patient_id = None
        for patient in patients:
            if patient[3] == phone_number:
                patient_id = patient[1]
                break
        
        if patient_id:
            self.db.save_message(
                patient_id, 'outgoing', 'sms', message, language,
                'none', '', 'System response'
            )
        
        return {"status": "success"}
    
    def receive_sms(self, phone_number, message_text):
        print(f"\nSMS RECEIVED from {phone_number}: {message_text}\n")
        
        patients = self.db.get_all_patients()
        patient = None
        for p in patients:
            if p[3] == phone_number:
                patient = p
                break
        
        if not patient:
            return {"error": "Patient not registered"}
        
        patient_id = patient[1]
        patient_lang = patient[4]
        
        analysis = self.ai_engine.analyze_text(message_text, patient_lang)
        response_message = analysis['response']
        
        self.db.save_message(
            patient_id, 'incoming', 'sms', message_text, patient_lang,
            analysis['risk_level'], ','.join(analysis['symptoms']), response_message
        )
        
        self.send_sms(phone_number, response_message, patient_lang)
        
        if analysis['risk_level'] == 'high':
            self._trigger_emergency(patient, message_text, analysis)
        
        return {
            "status": "processed",
            "risk_level": analysis['risk_level'],
            "response": response_message
        }
    
    def _trigger_emergency(self, patient, original_message, analysis):
        print(f"\nEMERGENCY ALERT! Patient: {patient[2]} ({patient[1]})")
        hospital_info = self.ai_engine.find_nearest_hospital(patient[5])
        self.send_sms(patient[3], f"HOSPITAL REFERRAL: {hospital_info}", patient[4])

class AfricaTalkingSandbox:
    @staticmethod
    def simulate_sms_flow():
        print("\nAfrica's Talking SMS Simulation")
    
    @staticmethod
    def simulate_voice_flow():
        print("\nAfrica's Talking Voice Simulation")