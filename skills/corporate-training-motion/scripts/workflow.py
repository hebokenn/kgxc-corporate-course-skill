#!/usr/bin/env python3
"""Portable entry point, also included in each editable course."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'workbench'))
from runtime import activate
activate()
from workflow import main
if __name__ == '__main__':
    try: main()
    except (ValueError, OSError) as exc: print(str(exc), file=sys.stderr); raise SystemExit(2)
