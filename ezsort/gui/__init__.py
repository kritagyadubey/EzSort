"""EzSort desktop application package.

Launch with ``python -m ezsort gui``, ``ezsort gui``, or the
``ezsort-gui`` console-script / Windows executable.
"""

from __future__ import annotations

import sys


def run() -> int:
    """Start the desktop app and return an exit code."""
    import importlib

    try:
        importlib.import_module("tkinter")
    except ImportError:
        print(
            "EzSort's desktop app needs tkinter, which normally ships with "
            "Python.\nInstall it with:  sudo apt install python3-tk  "
            "(Debian/Ubuntu)"
        )
        return 1

    from ezsort.gui.app import EzSortApp

    app = EzSortApp()
    return app.main_loop()


__all__ = ["run"]


if __name__ == "__main__":  # pragma: no cover
    sys.exit(run())
