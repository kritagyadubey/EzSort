"""Default category mappings and constants for EzSort."""

from __future__ import annotations

from ezsort import __version__

VERSION_STRING = f"EzSort version {__version__}"

DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "Images": [
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
        ".tiff", ".tif", ".svg", ".ico", ".heic", ".heif",
        ".raw", ".cr2", ".nef", ".psd", ".ai", ".eps",
    ],
    "Videos": [
        ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv",
        ".wmv", ".m4v", ".mpg", ".mpeg", ".3gp", ".ts",
    ],
    "Music": [
        ".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg",
        ".wma", ".opus", ".aiff", ".mid", ".midi",
    ],
    "Documents": [
        ".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt",
        ".pages", ".tex", ".md", ".markdown", ".log",
    ],
    "Spreadsheets": [
        ".xls", ".xlsx", ".csv", ".ods", ".numbers", ".tsv",
    ],
    "Presentations": [
        ".ppt", ".pptx", ".odp", ".key",
    ],
    "Archives": [
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
        ".xz", ".tgz", ".tar.gz", ".tar.bz2", ".tar.xz",
        ".dmg", ".iso", ".cab",
    ],
    "Applications": [
        ".exe", ".msi", ".deb", ".rpm", ".apk", ".app",
        ".pkg", ".snap", ".flatpak",
    ],
    "Code": [
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".kt",
        ".cpp", ".c", ".h", ".hpp", ".cs", ".rs", ".go",
        ".php", ".rb", ".swift", ".m", ".mm",
        ".html", ".css", ".scss", ".sass", ".less",
        ".json", ".xml", ".yaml", ".yml", ".toml", ".ini",
        ".sql", ".sh", ".bash", ".bat", ".ps1", ".cmd",
        ".r", ".lua", ".pl", ".ex", ".exs", ".erl",
        ".vue", ".svelte",
    ],
    "Fonts": [
        ".ttf", ".otf", ".woff", ".woff2", ".eot",
    ],
    "Ebooks": [
        ".epub", ".mobi", ".azw", ".azw3", ".fb2", ".djvu",
    ],
    "Torrents": [
        ".torrent",
    ],
}

CATEGORY_ORDER: list[str] = [
    "Images", "Videos", "Music", "Documents", "Spreadsheets",
    "Presentations", "Archives", "Applications", "Code",
    "Fonts", "Ebooks", "Torrents", "Others",
]

DEFAULT_EXCLUDED_DIRS: list[str] = [
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "EzSort",
]

# Extensions that indicate a file is still being downloaded/written.
# Files with these extensions are never touched by watch mode.
PARTIAL_DOWNLOAD_EXTENSIONS: list[str] = [
    ".crdownload", ".part", ".partial", ".opdownload",
    ".download", ".tmp", ".temp", ".!ut", ".bt!x",
]

# Windows device names that cannot be used as file/folder names.
WINDOWS_RESERVED_NAMES: set[str] = {
    "con", "prn", "aux", "nul",
    "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
    "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
}

# Characters that are illegal in file/folder names on Windows.
ILLEGAL_PATH_CHARS = '<>:"|?*'

BANNER = r"""
+------------------------------+
|            EzSort            |
|   Keep Your Files Sorted     |
+------------------------------+
"""
