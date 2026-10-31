"""PyInstaller entry point: the same as `python -m flowvoice`."""
import sys

from flowvoice.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
