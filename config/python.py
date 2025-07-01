""" python deps for this project """

import config.shared

install_requires: list[str] = [
    "google-api-python-client",
    "google-auth-httplib2",
    "google-auth-oauthlib",
    "pytconf",
]
build_requires: list[str] = config.shared.PBUILD
test_requires: list[str] = config.shared.PTEST
requires = install_requires + build_requires + test_requires
