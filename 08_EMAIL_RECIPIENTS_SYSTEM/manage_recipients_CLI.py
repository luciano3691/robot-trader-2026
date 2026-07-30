
#!/usr/bin/env python3
"""
Admin script to manage email recipients from command line.
Usage:
  python3 manage_recipients.py list
  python3 manage_recipients.py add-admin --email xxx --name xxx
  python3 manage_recipients.py remove --id xxx
  python3 manage_recipients.py update --id xxx --status active
"""

import json
import argparse
from datetime import datetime

DATABASE_FILE = 'DATABASE_RECIPIENTS.json'

def load_db():
    with open(DATABASE_FILE, 'r') as f:
        return json.load(f)

def save_db(db):
    db['last_updated'] = datetime.now().isoformat()
    with open(DATABASE_FILE, 'w') as f:
        json.dump(db, f, indent=2)

def list_recipients():
    db = load_db()
    
    print("\n📧 ADMIN RECIPIENTS:")
    print(f"{'ID':<15} {'Email':<35} {'Name':<25} {'Status':<10}")
    print("-" * 85)
    for r in db['admin_recipients']:
        print(f"{r['id']:<15} {r['email']:<35} {r['name']:<25} {r['status']:<10}")
    
    print(f"\n👥 CUSTOMER RECIPIENTS: {len(db['customer_recipients'])} (Launch: May 21)")

def add_admin_recipient(email, name, role, markets=['AZIONI']):
    db = load_db()
    
    new_id = f"admin_{len(db['admin_recipients']) + 1:03d}"
    
    new_recipient = {
        'id': new_id,
        'customer_id': 'SYSTEM_ADMIN',
        'email': email,
        'name': name,
        'role': role,
        'status': 'active',
        'report_format': 'excel',
        'frequency': 'daily',
        'markets': markets,
        'created_date': datetime.now().strftime('%Y-%m-%d'),
        'notes': f'Added via admin script'
    }
    
    db['admin_recipients'].append(new_recipient)
    save_db(db)
    
    print(f"✅ Added admin recipient: {new_id}")
    print(f"   Email: {email}")
    print(f"   Name: {name}")

def remove_recipient(recipient_id):
    db = load_db()
    
    # Remove from admin
    db['admin_recipients'] = [r for r in db['admin_recipients'] if r['id'] != recipient_id]
    
    # Remove from customers
    db['customer_recipients'] = [r for r in db['customer_recipients'] if r['id'] != recipient_id]
    
    save_db(db)
    print(f"✅ Removed recipient: {recipient_id}")

def update_recipient(recipient_id, **kwargs):
    db = load_db()
    
    found = False
    
    for r in db['admin_recipients']:
        if r['id'] == recipient_id:
            r.update(kwargs)
            found = True
            break
    
    if not found:
        for r in db['customer_recipients']:
            if r['id'] == recipient_id:
                r.update(kwargs)
                found = True
                break
    
    if found:
        save_db(db)
        print(f"✅ Updated recipient: {recipient_id}")
    else:
        print(f"❌ Recipient not found: {recipient_id}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Manage Robot Trader email recipients')
    subparsers = parser.add_subparsers(dest='command')
    
    # List command
    subparsers.add_parser('list', help='List all recipients')
    
    # Add admin command
    add_parser = subparsers.add_parser('add-admin', help='Add admin recipient')
    add_parser.add_argument('--email', required=True, help='Email address')
    add_parser.add_argument('--name', required=True, help='Full name')
    add_parser.add_argument('--role', default='Operations', help='Role')
    add_parser.add_argument('--markets', nargs='+', default=['AZIONI'], help='Markets')
    
    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove recipient')
    remove_parser.add_argument('--id', required=True, help='Recipient ID')
    
    # Update command
    update_parser = subparsers.add_parser('update', help='Update recipient')
    update_parser.add_argument('--id', required=True, help='Recipient ID')
    update_parser.add_argument('--status', help='Status (active/inactive)')
    
    args = parser.parse_args()
    
    if args.command == 'list':
        list_recipients()
    elif args.command == 'add-admin':
        add_admin_recipient(args.email, args.name, args.role, args.markets)
    elif args.command == 'remove':
        remove_recipient(args.id)
    elif args.command == 'update':
        update_recipient(args.id, status=args.status if args.status else None)
    else:
        parser.print_help()
