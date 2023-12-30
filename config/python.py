from typing import List


config_requies: List[str] = []
dev_requires: List[str] = [
    "pypitools",
]
install_requires: List[str] = [
    "google-api-python-client",
    "google-auth-httplib2",
    "google-auth-oauthlib",
    "pytconf",
]
make_requires: List[str] = [
    "pymakehelper",
    "pydmt",
    "pyclassifiers",
]
test_requires: List[str] = [
    "pylint",
    "pytest",
    "pytest-cov",
    "pyflakes",
    "flake8",
    "mypy",
]
requires = config_requires + install_requires + make_requires + test_requires
