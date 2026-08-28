""" auth.py """

import importlib
import logging
import os
import pickle

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from pygooglehelper.configs import ConfigAuth, ConfigRequest
from pygooglehelper.static import LOGGER_NAME
from pygooglehelper.util import ensure_folder, str_list_md5


def get_client_secret() -> str:
    """
    Find the client_secret.json for this application.

    Two places, in order:
      1. ~/.config/[app_name]/client_secret.json -- a credential the user put
         there themselves, which always wins so it can override the shipped one.
      2. the installed package folder -- the copy the build hook ships inside
         the wheel, so a plain `pip install` works with no user setup.

    An explicit "location" folder overrides both, for callers that keep the
    credential somewhere else entirely.
    """
    location: str = ConfigRequest.location
    app_name: str = ConfigRequest.app_name
    if location is not None:
        return os.path.join(location, "client_secret.json")
    if app_name is None:
        raise ValueError("one of ConfigRequest.app_name or ConfigRequest.location must be set")

    config_path = os.path.expanduser(f"~/.config/{app_name}/client_secret.json")
    if os.path.isfile(config_path):
        return config_path

    packaged = os.path.join(os.path.dirname(importlib.import_module(app_name).__file__), "client_secret.json")
    if os.path.isfile(packaged):
        return packaged

    raise FileNotFoundError(
        f"no client_secret.json for {app_name}: looked in {config_path} and {packaged}"
    )


def get_credentials(
) -> Credentials:
    """
    The file token.pickle stores the users access and refresh tokens, and is
    created automatically when the authorization flow completes for the first
    time.
    It is also updated when refreshing or when the scopes change.
    """
    scopes: list[str] = ConfigRequest.scopes
    host: str = ConfigAuth.host
    port: int = ConfigAuth.port
    authorization_prompt_message: str = ConfigAuth.authorization_prompt_message
    force: bool = ConfigAuth.force

    logger = logging.getLogger(LOGGER_NAME)
    credentials: Credentials | None = None
    md5_of_scopes = str_list_md5(scopes)
    token_filename = os.path.expanduser(f"~/.config/google_tokens/token-{md5_of_scopes}.pickle")
    logger.debug(f"reading credentials from [{token_filename}]")
    if force and os.access(token_filename, os.R_OK):
        os.unlink(token_filename)
    if os.access(token_filename, os.R_OK):
        with open(token_filename, "rb") as token_stream:
            credentials = pickle.load(token_stream)
    if credentials is None or not credentials.valid:
        if credentials is not None:
            if credentials.expired and credentials.refresh_token:
                logger.debug("refreshing credentials")
                credentials.refresh(Request())
        else:
            client_secret = get_client_secret()
            logger.debug(f"creating credentials from client secret at {client_secret}")
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secret, scopes,
            )
            credentials = flow.run_local_server(
                host=host,
                port=port,
                authorization_prompt_message=authorization_prompt_message,
            )
        logger.debug(f"creating a new token file [{token_filename}]")
        # there is a need to remove the old file if it exists since we chmod them so we cant overwrite them
        if os.access(token_filename, os.R_OK):
            os.unlink(token_filename)
        ensure_folder(token_filename)
        with open(token_filename, "wb") as token_stream:
            os.fchmod(token_stream.fileno(), 0o400)
            pickle.dump(credentials, token_stream)
    else:
        logger.debug(f"have valid credentials in [{token_filename}]")
    return credentials
