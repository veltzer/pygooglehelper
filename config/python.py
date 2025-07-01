""" python deps for this project """

import config.shared

install_requires: list[str] = [
    "google-api-python-client",
    "google-auth-httplib2",
    "google-auth-oauthlib",
    "pytconf",
]
build_requires: list[str] = [
    "hatch",
    "pydmt",
    "pymakehelper",
    "pycmdtools",
]
test_requires: list[str] = [
    "pylint",
    "pytest",
    "mypy",
    "ruff",
]
requires = install_requires + build_requires + test_requires
