"""Allow running EzSort as a module: python -m ezsort"""

import sys
from ezsort.cli import main

if __name__ == "__main__":
    sys.exit(main())
