"""Standalone utility to free ports 8000 and 5173 and clean orphaned processes."""
import sys
from pathlib import Path

# Add scripts directory to path to import from launcher
scripts_dir = Path(__file__).resolve().parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from launcher import clean_and_free_ports

if __name__ == "__main__":
    ports = [8000, 5173]
    if len(sys.argv) > 1:
        try:
            ports = [int(p) for p in sys.argv[1:]]
        except ValueError:
            pass
    clean_and_free_ports(*ports)
