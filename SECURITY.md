# Security Policy

## Reporting Vulnerabilities

If you discover a security vulnerability in EzSort, please report it responsibly.

**Do not** open a public GitHub issue for security vulnerabilities.

Instead, please email the maintainer directly with:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Security Principles

EzSort is designed with these security principles:

- **Local-only**: No files leave the user's machine
- **No network access**: Core features work offline
- **No deletion**: Files are never deleted, only moved
- **No overwriting**: Duplicate files are renamed, not overwritten
- **Permission handling**: Graceful handling of permission errors
- **Path validation**: Prevents path traversal attacks

## Scope

This security policy applies to the EzSort Python package distributed via GitHub.

## Updates

Security fixes will be released as patch versions (e.g., 0.1.1).
