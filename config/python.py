import config.project

package_name = config.project.project_name

console_scripts = [
]

setup_requires = [
]

run_requires = [
    "google-api-python-client",  # for google API
    "google-auth-httplib2",  # for google API
    "google-auth-oauthlib",  # for google API
    'pytconf',  # for command line parsing
]

test_requires = [
    'pylint',  # to check for lint errors
    'pytest',  # for testing
    'pytest-cov',  # for testing
    'pyflakes',  # for testing
    'flake8',  # for testing
    'pymakehelper',  # for the Makefile
]

dev_requires = [
    'pyclassifiers',  # for programmatic classifiers
    'pypitools',  # for upload etc
    'pydmt',  # for building
    'Sphinx',  # for the sphinx builder
]

install_requires = list(setup_requires)
install_requires.extend(run_requires)

python_requires = ">=3.6"

extras_require = {
    # ':python_version == "2.7"': ['futures'],  # for python2.7 backport of concurrent.futures
}
