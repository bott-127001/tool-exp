"""
Test script to verify backend doesn't auto-open browser
Run this to start backend and monitor what happens
"""
import subprocess
import sys
import time

print("="*70)
print("TESTING BACKEND STARTUP")
print("="*70)
print("\nStarting backend server...")
print("If a browser opens automatically, we'll see it in the output.")
print("Press Ctrl+C to stop.\n")

try:
    # Start the backend
    process = subprocess.Popen(
        [sys.executable, "main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # Monitor output for 10 seconds
    print("Monitoring for 10 seconds...")
    for i in range(10):
        output = process.stdout.readline()
        if output:
            print(output.strip())
        time.sleep(1)
    
    print("\n" + "="*70)
    print("If you saw 'LOGIN REQUEST RECEIVED' above, something is calling")
    print("the /auth/login endpoint automatically. This should NOT happen!")
    print("="*70)
    
except KeyboardInterrupt:
    print("\nStopping...")
    process.terminate()

