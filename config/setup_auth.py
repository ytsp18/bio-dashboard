#!/usr/bin/env python3
"""
Bio Dashboard - Authentication Setup Script

วิธีใช้:
    python setup_auth.py

Script นี้จะ:
1. สร้าง user accounts ตาม default
2. Generate password hash
3. อัพเดท config.yaml

หลังจากรันแล้วจะได้:
- username: admin, password: admin123
- username: operator, password: operator123

!!! เปลี่ยนรหัสผ่านก่อนใช้งานจริง !!!
"""

import os
import sys

def main():
    try:
        import streamlit_authenticator as stauth
        import yaml
    except ImportError:
        print("=" * 60)
        print("กรุณาติดตั้ง dependencies ก่อน:")
        print("  pip install streamlit-authenticator pyyaml")
        print("=" * 60)
        return

    print("=" * 60)
    print("Bio Dashboard - Authentication Setup")
    print("=" * 60)

    # Default users
    users = {
        'admin': {
            'email': 'admin@bio-dashboard.local',
            'name': 'Administrator',
            'password': 'admin123'
        },
        'operator': {
            'email': 'operator@bio-dashboard.local',
            'name': 'Operator User',
            'password': 'operator123'
        }
    }

    print("\nGenerating password hashes...")

    # Generate hashed passwords
    credentials = {'usernames': {}}

    for username, info in users.items():
        hashed = stauth.Hasher([info['password']]).generate()[0]
        credentials['usernames'][username] = {
            'email': info['email'],
            'name': info['name'],
            'password': hashed
        }
        print(f"  - {username}: OK")

    # Create config
    config = {
        'credentials': credentials,
        'cookie': {
            'expiry_days': 30,
            'key': 'bio_dashboard_secret_cookie_key_change_in_production_12345',
            'name': 'bio_dashboard_auth'
        },
        'pre-authorized': {
            'emails': ['admin@bio-dashboard.local']
        }
    }

    # Save config
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')

    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    print(f"\nSaved to: {config_path}")

    print("\n" + "=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print("\nDefault credentials:")
    print("-" * 40)
    for username, info in users.items():
        print(f"  Username: {username}")
        print(f"  Password: {info['password']}")
        print("-" * 40)

    print("\n!!! เปลี่ยนรหัสผ่านก่อนใช้งานจริง !!!")
    print("\nรัน Dashboard ด้วยคำสั่ง:")
    print("  cd bio_dashboard && streamlit run app.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
