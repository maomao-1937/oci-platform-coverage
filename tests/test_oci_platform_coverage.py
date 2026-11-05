import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, str(ROOT / "oci_platform_coverage.py")]
INDEX = "application/vnd.oci.image.index.v1+json"
MANIFEST = "application/vnd.oci.image.manifest.v1+json"
AMD64 = {"os": "linux", "architecture": "amd64"}
ARM = {"os": "linux", "architecture": "arm"}
ARM_V7 = {**ARM, "variant": "v7"}
UNKNOWN = {"os": "unknown", "architecture": "unknown"}


def descriptor(**overrides):
    return {"mediaType": MANIFEST, "digest": "sha256:" + "a" * 64,
            "size": 42, "platform": AMD64} | overrides


def image_index(*descriptors):
    return {"schemaVersion": 2, "mediaType": INDEX, "manifests": list(descriptors)}


class CoverageCLI(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.index = Path(temporary.name) / "private-index.json"
        self.requirements = Path(temporary.name) / "private-requirements.json"

    def command(self, index, requirements):
        for path, data in [(self.index, index), (self.requirements, requirements)]:
            path.write_bytes(data if isinstance(data, bytes) else json.dumps(data).encode("utf-8"))
        return [*CLI, str(self.index), str(self.requirements)]

    def run_cli(self, index, requirements):
        return subprocess.run(self.command(index, requirements), capture_output=True, timeout=5)

    def assert_invalid(self, index, requirements):
        result = self.run_cli(index, requirements)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr.strip(), b"error: invalid input")

    def test_unique_matches_use_input_ordinals_and_keep_metadata_private(self):
        index = image_index(descriptor(platform=ARM_V7), descriptor(annotations={"private": "secret"}))
        del index["mediaType"]
        result = self.run_cli(index, [AMD64, ARM_V7])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(json.loads(result.stdout), {
            "covered": 2, "missing": 0, "ambiguous": 0, "skipped": 0,
            "requirements": [{"ordinal": 1, "matches": [2]}, {"ordinal": 2, "matches": [1]}],
        })
        self.assertEqual(result.stdout, self.run_cli(index, [AMD64, ARM_V7]).stdout)

    def test_variant_is_exact_and_all_duplicate_candidates_are_reported(self):
        index = image_index(descriptor(platform=ARM_V7), descriptor(platform=ARM_V7), descriptor())
        result = self.run_cli(index, [ARM, ARM_V7, AMD64])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(json.loads(result.stdout), {
            "covered": 2, "missing": 1, "ambiguous": 1, "skipped": 0,
            "requirements": [{"ordinal": 1, "matches": []}, {"ordinal": 2, "matches": [1, 2]},
                             {"ordinal": 3, "matches": [3]}],
        })

    def test_skipped_descriptors_keep_later_ordinals(self):
        absent = descriptor()
        del absent["platform"]
        index = image_index(absent, descriptor(mediaType=INDEX), descriptor(platform=UNKNOWN),
                            descriptor(mediaType="example/other", platform=None), descriptor())
        result = self.run_cli(index, [AMD64, UNKNOWN])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "covered": 1, "missing": 1, "ambiguous": 0, "skipped": 4,
            "requirements": [{"ordinal": 1, "matches": [5]}, {"ordinal": 2, "matches": []}],
        })

    def test_index_and_descriptor_schema_errors(self):
        invalid = [[], {"schemaVersion": True, "manifests": []},
                   {"schemaVersion": 2.0, "manifests": []},
                   {"schemaVersion": 2, "mediaType": None, "manifests": []},
                   {"schemaVersion": 2, "manifests": {}}, image_index(None),
                   image_index(descriptor(mediaType=3)), image_index(descriptor(digest="sha256:" + "A" * 64)),
                   image_index(descriptor(digest="sha256:" + "b" * 63)),
                   image_index(descriptor(size=True)), image_index(descriptor(size=-1)),
                   image_index(descriptor(size=2**63)), image_index(descriptor(platform=None)),
                   image_index(descriptor(platform={"os": "linux"})),
                   image_index(descriptor(platform={**AMD64, "variant": "v8.1"})),
                   image_index(descriptor(mediaType=INDEX, size=-1))]
        for index in invalid:
            with self.subTest(index=index):
                self.assert_invalid(index, [AMD64])

    def test_requirement_objects_are_exact_nonempty_and_unique(self):
        for requirements in [[], {}, [AMD64, dict(reversed(list(AMD64.items())))],
                             [{**AMD64, "os": "Linux"}], [{**AMD64, "architecture": "é"}],
                             [{**AMD64, "variant": None}], [{**AMD64, "features": []}]]:
            with self.subTest(requirements=requirements):
                self.assert_invalid(image_index(descriptor()), requirements)

    def test_ignored_metadata_still_obeys_strict_json(self):
        prefix = b'{"schemaVersion":2,"manifests":[],"ignored":'
        for ignored in [b'{"x":1,"x":2}', b'NaN', b'Infinity', b'-Infinity', b'1e999',
                        b'"\\ud800"', b'{"\\udfff":1}', b'"\xff"']:
            with self.subTest(ignored=ignored):
                self.assert_invalid(prefix + ignored + b'}', [AMD64])
        self.assert_invalid(image_index(descriptor()), b'[{"os":"linux","architecture":"amd64","os":"linux"}]')

    def test_valid_ignored_metadata_and_integer_boundary(self):
        index = image_index(descriptor(size=2**63 - 1, platform={**AMD64, "os.version": "\\local"}))
        raw = json.dumps(index).encode("utf-8")[:-1] + b',"ignored":' + b'1' * 5000 + b'}'
        result = self.run_cli(raw, [AMD64])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_lexical_rejection_precedes_any_input_stat_or_open(self):
        probe = """
import sys
from unittest.mock import patch
import oci_platform_coverage as tool

with patch('os.stat', side_effect=AssertionError('stat called')), \
     patch('os.open', side_effect=AssertionError('open called')):
    raise SystemExit(tool.main(sys.argv[1:]))
"""
        forbidden = ["https://example.invalid/private", "data:private", r"\\host\share",
                     r"\/host\share", r"/\host/share", "//host/share", r"\\?\C:\private",
                     r"//./pipe/private", r"\??\C:\private", r"\SystemRoot\x", "/GlobalRoot/x",
                     "NUL.json", "folder/COM¹ .json",
                     "C:drive-relative", "local.json:stream", "-"]
        for path in forbidden:
            for arguments in [[path, "local.json"], ["local.json", path]]:
                with self.subTest(arguments=arguments):
                    result = subprocess.run([sys.executable, "-B", "-c", probe, *arguments], cwd=ROOT,
                                            capture_output=True, timeout=5)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(result.stdout, b"")
                    self.assertEqual(result.stderr.strip(), b"error: invalid input")

    def test_missing_directory_and_oversized_input(self):
        command = self.command(image_index(descriptor()), [AMD64])
        for bad_path in [self.index.with_name("missing"), self.index.parent]:
            result = subprocess.run([*CLI, str(bad_path), command[-1]], capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(result.stderr.strip(), b"error: invalid input")
        self.assert_invalid(b" " * (2**20 + 1), [AMD64])
        self.assert_invalid(image_index(descriptor()), b" " * (2**20 + 1))

    def test_wrong_arity_and_help_are_fixed(self):
        result = subprocess.run([*CLI, "private-argument"], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr.strip(), b"usage: oci_platform_coverage.py INDEX REQUIREMENTS")
        result = subprocess.run([*CLI, "--help"], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        self.assertIn(b"INDEX REQUIREMENTS", result.stdout)

    def test_real_closed_stdout_pipe_returns_neutral_output_error(self):
        command = self.command(image_index(descriptor()), [AMD64])
        read_end, write_end = os.pipe()
        os.close(read_end)
        try:
            result = subprocess.run(command, stdout=write_end, stderr=subprocess.PIPE, timeout=5)
        finally:
            os.close(write_end)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stderr.strip(), b"error: output failed")
