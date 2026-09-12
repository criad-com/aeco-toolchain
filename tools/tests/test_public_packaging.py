"""Public names must not create exceptions for private deployment data."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SWEEP = runpy.run_path(str(ROOT / "tools/term-sweep.py"))
REVISION = "47154dc7b5e28df623745495a7a508b69535ba24"


class PublicSweepCase(unittest.TestCase):
    def test_exact_public_org_is_allowed(self):
        for line in ("criad-com", "criad-com.", "github:criad-com/aeco-toolchain?ref=v0.4.0",
                     "https://github.com/criad-com/aeco-toolchain"):
            with self.subTest(line=line):
                self.assertFalse(SWEEP["has_private_term"]("README.md", line))

    def test_slug_does_not_allow_other_private_terms_or_near_matches(self):
        company = "Cr" + "iad"
        slug = "criad-com"
        for line in (company, "prefix-" + slug, slug + "-suffix",
                     "prefix" + slug, slug + ".suffix",
                     "criad-com " + company, "criad-com " + "10." + "1.2.3"):
            with self.subTest():
                self.assertTrue(SWEEP["has_private_term"]("README.md", line))

    def test_copyright_exception_is_exact_and_only_in_root_licence(self):
        notice = "Copyright (c) 2026 " + "Cr" + "iad"
        self.assertFalse(SWEEP["has_private_term"]("LICENSE", notice))
        self.assertTrue(SWEEP["has_private_term"]("README.md", notice))
        self.assertTrue(SWEEP["has_private_term"]("LICENSE", notice + " extra"))

    def test_registry_and_tracked_lockfile_are_swept(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "nix").mkdir()
            private_address = "10." + "1.2.3"
            for name in ("nix/registry.json", "flake.lock"):
                (root / name).write_text(private_address)
            output = io.StringIO()
            with mock.patch("subprocess.check_output", return_value=b"nix/registry.json\0flake.lock\0"), \
                    contextlib.redirect_stdout(output):
                self.assertTrue(SWEEP["sweep"](root))
            self.assertIn("term sweep: 2 findings", output.getvalue())
            self.assertNotIn(private_address, output.getvalue())


class RegistryCase(unittest.TestCase):
    def launch(self, registry_path=None):
        environment = {} if registry_path is None else {"AECO_NIX_REGISTRY": str(registry_path)}
        with mock.patch.dict(os.environ, environment, clear=True), \
                mock.patch("sys.argv", ["nix-local.py", "flake", "check", "--offline"]), \
                mock.patch("os.chdir"), mock.patch("os.execvp") as execute:
            runpy.run_path(str(ROOT / "tools/nix-local.py"), run_name="__main__")
        return execute.call_args.args[1]

    def test_public_template_matches_upstream_input(self):
        registry = json.loads((ROOT / "nix/registry.json").read_text())
        self.assertEqual(registry["flakes"][0]["from"], {
            "type": "github", "owner": "PixarAnimationStudios", "repo": "OpenUSD"})
        self.assertIn(f"github:PixarAnimationStudios/OpenUSD?rev={REVISION}",
                      (ROOT / "flake.nix").read_text())
        command = self.launch()
        self.assertEqual(command[-3:], ["--override-input", "openusd",
                         f"git+https://github.com/PixarAnimationStudios/OpenUSD.git?ref=dev&rev={REVISION}"])

    def test_external_registry_preserves_revision_and_caller_options(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = Path(temp) / "registry.json"
            registry.write_text(json.dumps({
                "flakes": [{"to": {"url": "https://mirror.example.org/OpenUSD.git"}}],
                "nixConfig": {"substituters": ["https://cache.example.org/"]}}))
            command = self.launch(registry)
        self.assertEqual(command[:4], ["nix", "--option", "substituters", "https://cache.example.org/"])
        self.assertIn("--offline", command)
        self.assertIn("--no-write-lock-file", command)
        self.assertEqual(command[-1], f"git+https://mirror.example.org/OpenUSD.git?ref=dev&rev={REVISION}")


if __name__ == "__main__":
    unittest.main()
