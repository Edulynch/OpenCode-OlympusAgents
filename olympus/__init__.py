"""Olympus operator CLI; canonical configuration remains in Olympus Core."""

import sys

# Supported entrypoints also pass -B, including before this package is imported.
sys.dont_write_bytecode = True
