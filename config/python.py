import config.project

package_name = config.project.project_name

dev_requires = [
    "pyclassifiers",
    "pypitools",
    "pydmt",
    "Sphinx",
]
install_requires = [
    "google-api-python-client",
    "google-auth-httplib2",
    "google-auth-oauthlib",
    "pytconf",
]
test_requires = [
    "pylint",
    "pytest",
    "pytest-cov",
    "pyflakes",
    "flake8",
    "pymakehelper",
]

python_requires = ">=3.10"

test_os = ["ubuntu-22.04"]
test_python = ["3.10"]
