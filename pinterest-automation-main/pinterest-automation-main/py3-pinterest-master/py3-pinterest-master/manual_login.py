#!/usr/bin/env python3
"""
Manual login script for Pinterest.
Opens Chrome browser for interactive login with CAPTCHA handling.
Saves cookies for later use.
"""
import os
import time
from py3pin.Pinterest import Pinterest

# Get credentials from environment
email = os.environ.get("PINTEREST_EMAIL", "kdkr666@gmail.com")
password = os.environ.get("PINTEREST_PASSWORD", "password@66")
username = os.environ.get("PINTEREST_USERNAME", "kdkr666")

print(f"Logging in with:")
print(f"  Email: {email}")
print(f"  Username: {username}")
print()

try:
    # Create Pinterest client
    pinterest = Pinterest(
        email=email,
        password=password,
        username=username,
        cred_root="data"
    )
    
    print("Opening Chrome browser for login...")
    print("Complete the login process in the browser window that opens.")
    print("If you see a CAPTCHA, please solve it manually.")
    print("This will wait up to 30 seconds...")
    print()
    
    # Perform login with VISIBLE browser window (headless=False) and longer wait time
    pinterest.login(headless=False, wait_time=30)
    
    # Give a moment for cookies to persist
    time.sleep(2)
    
    print("✓ Login successful!")
    print(f"✓ Cookies saved to data/{email}")
    print()
    print("You can now run the tests:")
    print("  python -m pytest tests/ -v")
    
except Exception as e:
    print(f"✗ Login failed: {e}")
    print()
    print("Troubleshooting:")
    print("1. Make sure Chrome is installed")
    print("2. Check your email and password are correct")
    print("3. Your Pinterest account may have 2FA enabled - check your email")
    import traceback
    traceback.print_exc()
    exit(1)
