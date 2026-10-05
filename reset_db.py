"""
Database Reset & Re-seeding Utility for NH-7 Landslide Risk Backend.
Usage:
    python reset_db.py
"""
import sys
from app.database import reset_db
from app.config import DB_PATH

def main():
    print(f"Purging and resetting database at: {DB_PATH} ...")
    reset_db()
    print("Database successfully reset and re-seeded with:")
    print("  - 18 NH-7 road segments (Rishikesh to Joshimath)")
    print("  - 3 initial subscriber profiles")
    print("  - 3 field hazard reports")
    print("  - 7 historical landslide records along NH-7")

if __name__ == "__main__":
    main()
