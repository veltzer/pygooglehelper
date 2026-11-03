""" register_hook.py """

from pytconf import register_function

from pygooglehelper.auth import check_token, get_credentials
from pygooglehelper.configs import ConfigAuth, ConfigRequest


def register_functions():
    register_function(
        function=get_credentials,
        description="Do the authentication procedure and get token for your app",
        name="auth",
        configs=[ConfigAuth, ConfigRequest],
    )
    register_function(
        function=check_token,
        description="Check whether the cached token is valid, refreshing it if expired (no browser)",
        name="check_token",
        configs=[ConfigRequest],
    )
