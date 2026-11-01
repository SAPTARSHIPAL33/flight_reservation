import os
import sys

# Ensure root directory is always on sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("  Starting AeroBook Flight Reservation API Server")
    print("  Listening on http://127.0.0.1:8000 and http://localhost:8000")
    print("=" * 60)
    try:
        uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)
    except Exception as e:
        print(f"\n[ERROR] Server terminated: {e}")
        input("Press Enter to exit...")
