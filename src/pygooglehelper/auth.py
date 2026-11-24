""" auth.py """

import importlib
import json
import logging
import os
import pickle
import subprocess
import sys
from typing import Any

from google.auth.exceptions import RefreshError, TransportError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from pygooglehelper.configs import ConfigAuth, ConfigRequest
from pygooglehelper.static import LOGGER_NAME
from pygooglehelper.util import ensure_folder, str_list_md5

PASS_TIMEOUT_SECONDS = 120


def _pass_entry(kind: str) -> str | None:
    """ the pass(1) entry name for this project and kind, or None when no project is set """
    project: str | None = ConfigRequest.gcp_project
    if not project:
        return None
    return f"gcp/{project}/{kind}"


def _pass_show(entry: str) -> str | None:
    """
    The content of a pass(1) entry, or None when pass is missing or the entry
    does not exist. No shell is involved and the content is never logged.
    """
    try:
        result = subprocess.run(
            ["pass", "show", entry],
            capture_output=True,
            text=True,
            check=False,
            timeout=PASS_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _pass_show_json(entry: str) -> dict[str, Any] | None:
    """ a pass(1) entry parsed as a JSON object, or None when absent or not one """
    content = _pass_show(entry)
    if content is None:
        return None
    try:
        parsed = json.loads(content)
    except ValueError:
        logging.getLogger(LOGGER_NAME).warning("pass entry [%s] is not valid JSON, ignoring it", entry)
        return None
    if not isinstance(parsed, dict):
        logging.getLogger(LOGGER_NAME).warning("pass entry [%s] is not a JSON object, ignoring it", entry)
        return None
    return parsed


def _pass_insert(entry: str, content: str) -> bool:
    """ overwrite a pass(1) entry, content on stdin so it never reaches argv or disk """
    try:
        result = subprocess.run(
            ["pass", "insert", "-m", "-f", entry],
            input=content,
            capture_output=True,
            text=True,
            check=False,
            timeout=PASS_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def get_pass_client_config() -> dict[str, Any] | None:
    """ the OAuth client config from gcp/[gcp_project]/oauth-client, or None """
    entry = _pass_entry("oauth-client")
    if entry is None:
        return None
    config = _pass_show_json(entry)
    if config is None:
        return None
    if "installed" not in config and "web" not in config:
        logging.getLogger(LOGGER_NAME).warning("pass entry [%s] is not a client_secret.json, ignoring it", entry)
        return None
    return config


def _token_to_pass(entry: str, credentials: Credentials) -> None:
    """
    Store the credentials in pass without the access token and expiry: those are
    short lived and rewriting them on every refresh would churn the git-tracked
    pass store.
    """
    info = json.loads(credentials.to_json())
    info.pop("token", None)
    info.pop("expiry", None)
    if _pass_insert(entry, json.dumps(info, indent=2) + "\n"):
        logging.getLogger(LOGGER_NAME).debug("stored token in pass entry [%s]", entry)
    else:
        logging.getLogger(LOGGER_NAME).warning(
            "could not store the token in pass entry [%s]; you will have to authorize again next time", entry,
        )


def _credentials_from_info(info: dict[str, Any], scopes: list[str]) -> Credentials | None:
    """ credentials from a stored authorized-user dict, or None when it does not cover the scopes """
    stored_scopes = info.get("scopes")
    if not isinstance(stored_scopes, list) or not set(scopes) <= set(stored_scopes):
        return None
    try:
        return Credentials.from_authorized_user_info(info, scopes)
    except ValueError:
        return None


def get_client_secret() -> str:
    """
    Find the client_secret.json for this application.

    (When ConfigRequest.gcp_project is set and pass(1) holds
    gcp/[gcp_project]/oauth-client, get_credentials uses that content directly
    and never calls this function.)

    Two places, in order:
      1. ~/.config/[app_name]/client_secret.json -- a credential the user put
         there themselves, which always wins so it can override the shipped one.
      2. the installed package folder -- the copy the build hook ships inside
         the wheel, so a plain `pip install` works with no user setup.

    An explicit "location" folder overrides both, for callers that keep the
    credential somewhere else entirely.
    """
    location: str | None = ConfigRequest.location
    app_name: str | None = ConfigRequest.app_name
    if location is not None:
        return os.path.join(location, "client_secret.json")
    if app_name is None:
        raise ValueError("one of ConfigRequest.app_name or ConfigRequest.location must be set")

    config_path = os.path.expanduser(f"~/.config/{app_name}/client_secret.json")
    if os.path.isfile(config_path):
        return config_path

    packaged = None
    module_file = importlib.import_module(app_name).__file__
    if module_file is not None:
        packaged = os.path.join(os.path.dirname(module_file), "client_secret.json")
        if os.path.isfile(packaged):
            return packaged

    raise FileNotFoundError(
        f"no client_secret.json for {app_name}: looked in {config_path} and {packaged}"
    )


def get_token_filename() -> str:
    """ the pickle that caches the tokens for the scopes in ConfigRequest """
    md5_of_scopes = str_list_md5(ConfigRequest.scopes)
    return os.path.expanduser(f"~/.config/google_tokens/token-{md5_of_scopes}.pickle")


def check_token() -> None:
    """
    Check that the cached token is usable without any user interaction.

    A still-valid access token is reported as is; an expired one is refreshed
    with the refresh token, which is what proves the refresh token still works
    (and counts as use of the OAuth client under Google's inactivity policy).
    The refreshed access token is not written back: this is a check, and the
    token file may be a symlink that a rewrite would replace. Only a changed
    refresh token is saved to pass. Exits with status 1 when the token is
    missing or cannot be refreshed.
    """
    token_entry = _pass_entry("token")
    credentials: Credentials | None = None
    stored_refresh_token: str | None = None
    if token_entry is not None:
        info = _pass_show_json(token_entry)
        if info is not None:
            stored_refresh_token = info.get("refresh_token")
            credentials = _credentials_from_info(info, ConfigRequest.scopes)
            if credentials is None:
                print(f"Token: INVALID (pass entry {token_entry} does not cover the scopes). Run 'auth --force'.", file=sys.stderr)
                sys.exit(1)
    if credentials is None:
        token_filename = get_token_filename()
        if not os.access(token_filename, os.R_OK):
            print(f"Token: MISSING ({token_filename}). Run 'auth'.", file=sys.stderr)
            sys.exit(1)
        with open(token_filename, "rb") as token_stream:
            credentials = pickle.load(token_stream)
    assert credentials is not None
    if not credentials.valid:
        if not credentials.refresh_token:
            print("Token: INVALID (expired and has no refresh token). Run 'auth --force'.", file=sys.stderr)
            sys.exit(1)
        try:
            credentials.refresh(Request())
        except RefreshError as e:
            print(f"Token: INVALID ({e}). Run 'auth --force'.", file=sys.stderr)
            sys.exit(1)
        except TransportError as e:
            print(f"Token: UNKNOWN (could not reach Google: {e})", file=sys.stderr)
            sys.exit(1)
        if token_entry is not None and stored_refresh_token is not None and credentials.refresh_token != stored_refresh_token:
            _token_to_pass(token_entry, credentials)
    print(f"Token: VALID (access token expires {credentials.expiry} UTC)")


def _authorize(client_config: dict[str, Any] | None) -> Credentials:
    """ run the interactive flow, from the pass client config when we have one, else from the files """
    scopes: list[str] = ConfigRequest.scopes
    logger = logging.getLogger(LOGGER_NAME)
    if client_config is not None:
        logger.debug("creating credentials from the client config in pass")
        flow = InstalledAppFlow.from_client_config(client_config, scopes)
    else:
        client_secret = get_client_secret()
        logger.debug("creating credentials from client secret at %s", client_secret)
        flow = InstalledAppFlow.from_client_secrets_file(client_secret, scopes)
    new_credentials = flow.run_local_server(
        host=ConfigAuth.host,
        port=ConfigAuth.port,
        authorization_prompt_message=ConfigAuth.authorization_prompt_message,
    )
    if not isinstance(new_credentials, Credentials):
        raise TypeError(f"unexpected credentials type [{type(new_credentials).__name__}]")
    return new_credentials


def _get_credentials_pass(token_entry: str, token_info: dict[str, Any] | None, client_config: dict[str, Any] | None) -> Credentials:
    """
    Credentials kept in pass. Access tokens are refreshed in memory only; pass is
    written after a fresh authorization or when the refresh token itself changed.
    """
    logger = logging.getLogger(LOGGER_NAME)
    credentials: Credentials | None = None
    if token_info is not None and not ConfigAuth.force:
        credentials = _credentials_from_info(token_info, ConfigRequest.scopes)
        if credentials is None:
            logger.debug("stored token does not cover the requested scopes, authorizing again")
    if credentials is not None and not credentials.valid and not credentials.refresh_token:
        logger.debug("stored token is unusable and cannot be refreshed, authorizing again")
        credentials = None
    if credentials is None:
        credentials = _authorize(client_config)
        _token_to_pass(token_entry, credentials)
        return credentials
    if not credentials.valid:
        logger.debug("refreshing credentials")
        credentials.refresh(Request())
        if token_info is not None and credentials.refresh_token != token_info.get("refresh_token"):
            _token_to_pass(token_entry, credentials)
    return credentials


def get_credentials(
) -> Credentials:
    """
    Credentials for ConfigRequest.scopes.

    When ConfigRequest.gcp_project is set and pass(1) has gcp/[gcp_project]/oauth-client
    or gcp/[gcp_project]/token, both the OAuth client and the token live in pass
    and nothing is written to disk. Otherwise (no project, no pass, no such
    entries) the token pickle stores the users access and refresh tokens; it is
    created automatically when the authorization flow completes for the first
    time and is also updated when refreshing or when the scopes change.
    """
    token_entry = _pass_entry("token")
    if token_entry is not None:
        client_config = get_pass_client_config()
        token_info = _pass_show_json(token_entry)
        if client_config is not None or token_info is not None:
            return _get_credentials_pass(token_entry, token_info, client_config)

    logger = logging.getLogger(LOGGER_NAME)
    credentials: Credentials | None = None
    token_filename = get_token_filename()
    logger.debug("reading credentials from [%s]", token_filename)
    if ConfigAuth.force and os.access(token_filename, os.R_OK):
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
            credentials = _authorize(None)
        logger.debug("creating a new token file [%s]", token_filename)
        # there is a need to remove the old file if it exists since we chmod them so we cant overwrite them
        if os.access(token_filename, os.R_OK):
            os.unlink(token_filename)
        ensure_folder(token_filename)
        with open(token_filename, "wb") as token_stream:
            os.fchmod(token_stream.fileno(), 0o400)
            pickle.dump(credentials, token_stream)
    else:
        logger.debug("have valid credentials in [%s]", token_filename)
    assert credentials is not None
    return credentials
