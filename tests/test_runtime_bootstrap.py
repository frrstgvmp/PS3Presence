from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import runtime_bootstrap


class RuntimeBootstrapTests(unittest.TestCase):
    def test_removes_host_native_tools_but_preserves_python_and_user_paths(self):
        paths = [
            r"C:\Windows\System32",
            r"C:\Users\person\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin",
            r"C:\Users\person\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\libheif\libheif\bin",
            r"C:\Users\person\.cache\codex-runtimes\codex-primary-runtime\dependencies\python",
            r"C:\Tools\poppler\bin",
        ]
        cleaned = runtime_bootstrap.clean_native_path(os.pathsep.join(paths))
        self.assertEqual(cleaned.split(os.pathsep), [paths[0], paths[3], paths[4]])

    def test_handles_stay_alive_and_bootstrap_is_idempotent(self):
        with patch.object(runtime_bootstrap, "_PREPARED", False), \
             patch.object(runtime_bootstrap, "_DLL_HANDLES", []), \
             patch.object(runtime_bootstrap.os, "name", "nt"), \
             patch.object(runtime_bootstrap.Path, "is_dir", return_value=True), \
             patch.object(runtime_bootstrap.os, "add_dll_directory", create=True) as add, \
             patch.dict(os.environ, {"PATH": "original-path"}):
            runtime_bootstrap.prepare_native_libraries()
            calls = add.call_count
            self.assertGreater(calls, 0)
            self.assertEqual(len(runtime_bootstrap._DLL_HANDLES), calls)
            runtime_bootstrap.prepare_native_libraries()
            self.assertEqual(add.call_count, calls)


if __name__ == "__main__":
    unittest.main()
