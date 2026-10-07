from __future__ import annotations

import ast
from pathlib import Path
import unittest

from app_metadata import RELEASE_VERSION, VERSION


class ReleaseMetadataTests(unittest.TestCase):
    def test_beta_display_and_release_identifier_are_consistent(self):
        self.assertEqual(RELEASE_VERSION, VERSION.replace(" ", "-"))
        self.assertRegex(RELEASE_VERSION, r"^\d+\.\d+\.\d+-beta$")
        self.assertTrue(VERSION.endswith(" beta"))

    def test_windows_metadata_matches_display_and_marks_prerelease(self):
        project = Path(__file__).resolve().parents[1]
        tree = ast.parse((project / "packaging" / "version_info.txt").read_text(encoding="utf-8"))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
        fixed = next(node for node in calls if node.func.id == "FixedFileInfo")
        fields = {kw.arg: ast.literal_eval(kw.value) for kw in fixed.keywords}
        expected = (*map(int, VERSION.split()[0].split(".")), 0)
        self.assertEqual(fields["filevers"], expected)
        self.assertEqual(fields["prodvers"], expected)
        self.assertTrue(fields["flags"] & 0x2)
        strings = {ast.literal_eval(node.args[0]): ast.literal_eval(node.args[1])
                   for node in calls if node.func.id == "StringStruct"}
        self.assertEqual(strings["FileVersion"], VERSION)
        self.assertEqual(strings["ProductVersion"], VERSION)


if __name__ == "__main__":
    unittest.main()
