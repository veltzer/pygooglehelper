"""Behavioural tests for pygooglehelper's pure helpers."""

import hashlib
import os
import tempfile
import unittest

from pygooglehelper import util


class StrListMd5Tests(unittest.TestCase):
    def test_matches_hashlib_of_joined(self):
        scopes = ["https://example/a", "https://example/b"]
        want = hashlib.md5(",".join(scopes).encode()).hexdigest()
        self.assertEqual(util.str_list_md5(scopes), want)

    def test_order_matters(self):
        a = util.str_list_md5(["x", "y"])
        b = util.str_list_md5(["y", "x"])
        self.assertNotEqual(a, b)

    def test_empty_list(self):
        self.assertEqual(util.str_list_md5([]), hashlib.md5(b"").hexdigest())


class EnsureFolderTests(unittest.TestCase):
    def test_creates_missing_parent(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "a", "b", "file.txt")
            util.ensure_folder(target)
            self.assertTrue(os.path.isdir(os.path.join(d, "a", "b")))

    def test_existing_parent_is_noop(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "file.txt")
            util.ensure_folder(target)  # parent d already exists
            self.assertTrue(os.path.isdir(d))
