"""Read-only operator entrypoint: python -B -m olympus."""

import sys

if sys.version_info < (3, 11):
    print("Olympus requires Python 3.11 or newer.", file=sys.stderr)
    raise SystemExit(3)

from .cli import main

raise SystemExit(main())
