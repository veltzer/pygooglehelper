""" util.py """

import hashlib
import os


def str_list_md5(scopes: list[str]) -> str:
    all_string = ",".join(scopes)
    m = hashlib.md5(all_string.encode())
    return m.hexdigest()


def ensure_folder(filename: str) -> None:
    folder = os.path.dirname(filename)
    if not os.path.exists(folder):
        os.makedirs(os.path.dirname(filename))
