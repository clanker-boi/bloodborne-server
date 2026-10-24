"""Dependency-install separation and fast toolchain CLI unit tests.

Do not require Conan/Qt or Bloodborne; fake external commands in dry-run tests.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "yt.py"
spec = importlib.util.spec_from_file_location("yt_build", SOURCE)
yt = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(yt)


class BuildCliTests(unittest.TestCase):
    def test_output_paths_are_config_and_component_specific(self):
        self.assertEqual(yt.folder("server", "Release"),
                         yt.OUT / "server" / "release")
        self.assertNotEqual(yt.folder("server", "Debug"),
                            yt.folder("server", "Release"))

    def test_conan_install_makes_separate_generators(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(yt, "OUT", Path(temp)), \
                 patch.object(yt, "verify_tools"), patch.object(yt, "run") as run:
                yt.deps("server", "Release", build_policy="never", offline=False)
                args = run.call_args.args
                self.assertIn("--build=never", args)
                self.assertIn("&:with_server=True", args)
                self.assertIn("&:with_native=False", args)
                self.assertIn("--output-folder", args)

    def test_configure_reuses_prepared_dependencies(self):
        with tempfile.TemporaryDirectory() as temp:
            generator = Path(temp) / "conan_toolchain.cmake"
            generator.write_text("unused in mocked configure")
            with patch.object(yt, "deps") as deps, \
                 patch.object(yt, "verify_tools"), \
                 patch.object(yt.shutil, "which", return_value="/usr/bin/sccache"), \
                 patch.object(yt, "generated_toolchain", return_value=generator), \
                 patch.object(yt, "run") as run:
                yt.configure("server", "Release", reuse_deps=True,
                             build_policy="never", offline=False,
                             linker="mold", sccache=True,
                             compile_jobs=4, link_jobs=1)
                deps.assert_not_called()
                args = run.call_args.args
                self.assertIn("-DYT_LINKER=mold", args)
                self.assertIn("-DYT_COMPILE_JOBS=4", args)
                self.assertIn("-DYT_LINK_JOBS=1", args)

    def test_configure_installs_dependencies_when_not_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            generator = Path(temp) / "conan_toolchain.cmake"
            generator.write_text("")
            with patch.object(yt, "deps") as deps, \
                 patch.object(yt, "verify_tools"), \
                 patch.object(yt, "generated_toolchain", return_value=generator), \
                 patch.object(yt, "run"):
                yt.configure("server", "Release", reuse_deps=False,
                             build_policy="missing", offline=False, linker="default",
                             sccache=False, compile_jobs=0, link_jobs=0)
                deps.assert_called_once()

    def test_missing_toolchain_fails_clearly(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(yt, "OUT", Path(temp)):
                with self.assertRaises(SystemExit):
                    yt.generated_toolchain("server", "Release")


if __name__ == "__main__":
    unittest.main()
