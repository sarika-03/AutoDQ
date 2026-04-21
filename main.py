"""
main.py
Wrapper to run the CLI from the project root.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from main import main

if __name__ == "__main__":
    main()
