# TOFIX

Findings from a code scan on 2026-10-04.

## Medium

- `src/pygooglehelper/auth.py:74` - when a cached token is invalid but cannot be refreshed (not expired, or expired with no `refresh_token`), the `if credentials is not None` branch does nothing, and the still-invalid credentials are written back to the token file (line 97) and returned; fall through to the `InstalledAppFlow` re-authorization when refresh is not possible.

## Low

- `pyproject.toml:98` - the mypy override sets `ignore_missing_imports` for `pygooglehelper.*`, the package itself, which hides real import errors in its own modules; remove that entry (the code is in `src` on `mypy_path`).
- `pyproject.toml:89` - `mypy_path = "src:python:scripts"` names `python` and `scripts` directories that do not exist; reduce to `src`.
- `src/pygooglehelper/auth.py:41` - `importlib.import_module(app_name)` raises `ModuleNotFoundError` when `app_name` is not an importable module (e.g. contains `-`), instead of the `FileNotFoundError` the docstring and line 45 promise; catch it and fall through to the error.
