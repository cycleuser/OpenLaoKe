#!/usr/bin/env python3
"""Test Firefox launch with Selenium."""

import tempfile

from selenium import webdriver
from selenium.webdriver.firefox.options import Options

print("Testing Firefox launch...")

# Setup Firefox options
options = Options()
profile_dir = tempfile.mkdtemp(prefix="test-firefox-")
options.add_argument("-profile")
options.add_argument(profile_dir)

# Don't use headless - we want to see the browser
# options.add_argument("-headless")

print(f"Profile dir: {profile_dir}")
print("Launching Firefox...")

try:
    # Launch Firefox
    driver = webdriver.Firefox(options=options)

    print("✓ Firefox launched successfully!")
    print("Opening login page...")

    # Open a test page
    driver.get("https://chat.deepseek.com")

    print("✓ Page loaded. Browser should be visible.")
    print("Press Ctrl+C to close...")

    # Keep browser open
    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    driver.quit()
    print("✓ Firefox closed")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
