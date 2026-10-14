"""Allow running the desktop app as a module: python -m ezsort.gui"""

import sys

from ezsort.gui import run

if __name__ == "__main__":
    sys.exit(run())
