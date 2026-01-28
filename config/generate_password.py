"""
Script to generate hashed passwords for config.yaml

Usage:
    python generate_password.py

Then copy the hashed password to config.yaml
"""
import streamlit_authenticator as stauth

def main():
    print("=" * 50)
    print("Bio Dashboard - Password Hash Generator")
    print("=" * 50)

    password = input("Enter password to hash: ")

    if not password:
        print("Error: Password cannot be empty")
        return

    # Generate hashed password
    hashed_password = stauth.Hasher([password]).generate()[0]

    print("\n" + "=" * 50)
    print("Hashed Password:")
    print("=" * 50)
    print(hashed_password)
    print("\nCopy this hash and paste it in config.yaml")
    print("=" * 50)

if __name__ == "__main__":
    main()
