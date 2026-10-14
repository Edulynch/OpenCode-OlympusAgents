#!/usr/bin/env python3
"""Launch Olympus from this checkout, independently of the working directory."""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
if sys.version_info < (3, 11):
    print("Olympus requires Python 3.11 or newer.", file=sys.stderr)
    raise SystemExit(3)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from olympus.cli import main

raise SystemExit(main())
