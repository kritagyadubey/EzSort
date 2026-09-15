# Contributing to EzSort

Thank you for your interest in contributing to EzSort!

## How to Contribute

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run the tests: `pytest`
5. Commit your changes: `git commit -m "Add my feature"`
6. Push to your fork: `git push origin feature/my-feature`
7. Open a Pull Request

## Development Setup

```bash
git clone https://github.com/kritagyadubey/EzSort.git
cd EzSort
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -e ".[dev]"
pytest
```

## Guidelines

- Write tests for new features
- Follow PEP 8 style
- Keep functions small and focused
- Add docstrings to public functions
- Update documentation for user-facing changes

## Reporting Bugs

Use the [Bug Report template](https://github.com/kritagyadubey/EzSort/issues/new?template=bug_report.md).

## Suggesting Features

Use the [Feature Request template](https://github.com/kritagyadubey/EzSort/issues/new?template=feature_request.md).

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
