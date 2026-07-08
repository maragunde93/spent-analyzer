#!/usr/bin/env python3
import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.local_auth import hash_password


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a Spent Analyzer local auth password hash.")
    parser.add_argument("--password", help="Password to hash. Omit to be prompted without echo.")
    args = parser.parse_args()
    password = args.password or getpass.getpass("Password: ")
    if len(password) < 12:
        print("Use at least 12 characters for the production password.", file=sys.stderr)
        return 1
    print(hash_password(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
