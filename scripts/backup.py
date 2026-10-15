"""Consistent SQLite backup, including WAL, with private evidence manifest."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3

parser = argparse.ArgumentParser()
parser.add_argument("--source", default="data/civicsignal.db")
parser.add_argument("--destination", required=True, help="New empty backup directory")
args = parser.parse_args()
source = Path(args.source).resolve()
destination = Path(args.destination).resolve()
if not source.is_file():
    raise SystemExit("Source database does not exist.")
if destination.exists():
    raise SystemExit("Backup destination must not already exist; choose a new directory.")
destination.mkdir(parents=True)
with sqlite3.connect(source) as live, sqlite3.connect(destination / "civicsignal.db") as backup:
    live.backup(backup)
evidence = source.parent / "private-evidence"
if evidence.is_dir():
    shutil.copytree(evidence, destination / "private-evidence")
(destination / "manifest.json").write_text(json.dumps({"created_at": datetime.now(timezone.utc).isoformat(), "source": str(source), "private_data": True}, indent=2))
print(f"Private backup created: {destination}")
