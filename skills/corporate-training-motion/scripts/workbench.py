#!/usr/bin/env python3
"""Import a supported course into an editable copy, or open its local workbench."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'workbench'))
from backend import main
if __name__ == '__main__':
    main()
