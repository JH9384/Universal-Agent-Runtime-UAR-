"""Smoke tests for UOR artifact management scripts.

Covers fetch_uor_artifacts.py and validate_uor_alignment.py
without requiring real network or UOR Foundation releases.
"""

import json
from unittest.mock import patch, MagicMock

import pytest

# Fetch script
from scripts.fetch_uor_artifacts import (
    load_digests,
    ensure_tag_matches_version,
    download,
    sha256,
)

# Validate script
from scripts.validate_uor_alignment import (
    _ensure_cache_dir,
    _sample_event,
    validate_shacl,
)


class TestLoadDigests:
    def test_missing_file(self, tmp_path):
        with patch(
            "scripts.fetch_uor_artifacts.DIGESTS_PATH", tmp_path / "nope"
        ):
            with pytest.raises(SystemExit):
                load_digests("v1.0.0")

    def test_tag_not_found(self, tmp_path):
        digests = {"other": {"a": "b"}}
        path = tmp_path / "DIGESTS.json"
        path.write_text(json.dumps(digests))
        with patch("scripts.fetch_uor_artifacts.DIGESTS_PATH", path):
            with pytest.raises(SystemExit):
                load_digests("v1.0.0")

    def test_success(self, tmp_path):
        digests = {"v1.0.0": {"artifact.json": "abcd" * 16}}
        path = tmp_path / "DIGESTS.json"
        path.write_text(json.dumps(digests))
        with patch("scripts.fetch_uor_artifacts.DIGESTS_PATH", path):
            result = load_digests("v1.0.0")
            assert result == {"artifact.json": "abcd" * 16}


class TestEnsureTagMatchesVersion:
    def test_missing_version_file(self, tmp_path):
        with patch(
            "scripts.fetch_uor_artifacts.VERSION_PATH",
            tmp_path / "VERSION",
        ):
            # Should not raise
            ensure_tag_matches_version("v1.0.0")

    def test_matching_version(self, tmp_path):
        version_path = tmp_path / "VERSION"
        version_path.write_text("v1.0.0")
        with patch("scripts.fetch_uor_artifacts.VERSION_PATH", version_path):
            ensure_tag_matches_version("v1.0.0")

    def test_mismatch_version(self, tmp_path):
        version_path = tmp_path / "VERSION"
        version_path.write_text("v2.0.0")
        with patch("scripts.fetch_uor_artifacts.VERSION_PATH", version_path):
            with pytest.raises(SystemExit):
                ensure_tag_matches_version("v1.0.0")


class TestDownload:
    def test_download_timeout(self):
        with patch("scripts.fetch_uor_artifacts.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"test data"
            mock_urlopen.return_value.__enter__ = lambda s: s
            mock_urlopen.return_value.__exit__ = lambda s, *a: None
            mock_urlopen.return_value.read = mock_resp.read
            result = download("https://example.com/file")
            assert result == b"test data"
            mock_urlopen.assert_called_once()
            _, kwargs = mock_urlopen.call_args
            assert kwargs.get("timeout") == 60


class TestSha256:
    def test_basic(self):
        assert sha256(b"hello") == (
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        )


class TestSampleEvent:
    def test_structure(self):
        ev = _sample_event()
        assert ev["event_type"] == "sample"
        assert ev["run_id"] == "run-uor-validate"
        assert ev["payload"]["demo"] is True


class TestEnsureCacheDir:
    def test_missing_cache(self, tmp_path):
        with pytest.raises(SystemExit):
            _ensure_cache_dir("v999.0.0")


class TestValidateShacl:
    @staticmethod
    def _write_graphs(tmp_path, property_path="ex:name"):
        (tmp_path / "uor.foundation.ttl").write_text(
            """@prefix ex: <https://example.test/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
ex:Thing a owl:Class .
ex:name a owl:DatatypeProperty .
"""
        )
        (tmp_path / "uor.shapes.ttl").write_text(
            f"""@prefix ex: <https://example.test/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
ex:ThingShape a sh:NodeShape ;
    sh:targetClass ex:Thing ;
    sh:property [ sh:path {property_path} ; sh:datatype xsd:string ] .
"""
        )

    def test_well_formed_shapes_resolve_against_ontology(self, tmp_path):
        self._write_graphs(tmp_path)
        validate_shacl(tmp_path)

    def test_missing_ontology_property_fails(self, tmp_path):
        self._write_graphs(tmp_path, property_path="ex:missing")
        with pytest.raises(SystemExit, match="missing property paths"):
            validate_shacl(tmp_path)
