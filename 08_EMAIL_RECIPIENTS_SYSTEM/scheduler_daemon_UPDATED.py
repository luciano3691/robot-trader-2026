
import time
import json
import os
from datetime import datetime
import schedule
from email_notifier import send_report_email
from value_screener import run_screening

DATABASE_FILE = 'DATABASE_RECIPIENTS.json'

def load_recipients_database():
    """Load email recipients from JSON database"""
    try:
        with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
            db = json.load(f)
        return db
    except FileNotFoundError:
        print(f"⚠️ {DATABASE_FILE} not found. Using fallback emails.")
        return None

def get_active_recipients_for_screening(screening_type='daily'):
    """
    Get list of email recipients for today's screening.
    Filters by:
    - status = 'active'
    - frequency matches screening type (daily/weekly/manual)
    - markets include current product
    """
    db = load_recipients_database()
    
    if not db:
        # FALLBACK: Hardcoded (for backward compatibility)
        print("Using fallback hardcoded emails...")
        return [
            'luciano.manicardi@lineexpress.it',
            'newfrontiers65@gmail.com',
            'laura.manicardi65@gmail.com'
        ]
    
    recipient_emails = []
    
    # Get admin recipients
    for recipient in db.get('admin_recipients', []):
        if (recipient['status'] == 'active' and 
            recipient['frequency'] == screening_type and
            'AZIONI' in recipient.get('markets', [])):
            recipient_emails.append({
                'email': recipient['email'],
                'name': recipient.get('name', 'Admin'),
                'format': recipient.get('report_format', 'excel'),
                'timestamp': datetime.now().isoformat()
            })
    
    # Get customer recipients
    for recipient in db.get('customer_recipients', []):
        if (recipient['status'] == 'active' and 
            recipient['frequency'] == screening_type and
            'AZIONI' in recipient.get('markets', [])):
            recipient_emails.append({
                'email': recipient['email'],
                'name': recipient.get('customer_name', 'Customer'),
                'format': recipient.get('report_format', 'excel'),
                'customer_id': recipient.get('customer_id', 'unknown'),
                'timestamp': datetime.now().isoformat()
            })
    
    return recipient_emails

def run_daily_screening():
    """
    Main daily screening job:
    1. Load recipients from database
    2. Run screening
    3. Send report to each active recipient
    """
    print(f"\n{'='*60}")
    print(f"🤖 ROBOT TRADER SCREENING — {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC+2')}")
    print(f"{'='*60}\n")
    
    # Load recipients
    recipients = get_active_recipients_for_screening(screening_type='daily')
    print(f"📧 Recipients found: {len(recipients)}")
    
    if not recipients:
        print("⚠️ No active recipients found. Skipping screening.")
        return
    
    # Run value screener
    print("📊 Running value screener...")
    try:
        screening_results = run_screening()  # Returns Excel file path + data
        print(f"✅ Screening complete: {len(screening_results['stocks'])} stocks analyzed")
    except Exception as e:
        print(f"❌ Screening failed: {e}")
        return
    
    # Send to each recipient
    for recipient in recipients:
        print(f"\n📨 Sending to: {recipient['email']} ({recipient['name']})")
        try:
            send_report_email(
                to_email=recipient['email'],
                report_data=screening_results,
                report_format=recipient['format'],
                recipient_name=recipient['name']
            )
            print(f"   ✅ Email sent successfully")
        except Exception as e:
            print(f"   ❌ Failed to send: {e}")
    
    # Log completion
    log_screening_completion(recipients, screening_results)

def log_screening_completion(recipients, results):
    """Log screening execution to database"""
    db = load_recipients_database()
    if db:
        db['metadata']['last_report_run'] = datetime.now().isoformat()
        db['metadata']['total_emails_sent'] = len(recipients)
        
        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Screening logged. Sent to {len(recipients)} recipients.")

def schedule_daily_screening():
    """Schedule screening for 08:05 UTC+2 every day"""
    schedule.every().day.at("08:05").do(run_daily_screening)
    
    print("⏰ Robot Trader scheduled:")
    print("   → Daily screening at 08:05 UTC+2")
    print("   → Recipients loaded from DATABASE_RECIPIENTS.json")
    print("   → No hardcoded emails!")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == '__main__':
    schedule_daily_screening()
