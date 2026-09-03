from pathlib import Path
import pytest

from meet_tools.signer import prepare_firefox_staging, run_web_ext_lint, sign_firefox_addon


def test_prepare_staging_manifest(tmp_path):
    staging = tmp_path / "staging"
    res = prepare_firefox_staging(
        extension_dir=Path(__file__).resolve().parent.parent / "extension",
        staging_dir=staging,
        addon_id="test-meet@domain.com"
    )
    assert (staging / "manifest.json").exists()
    assert (staging / "content.js").exists()

    import json
    with open(staging / "manifest.json") as f:
        data = json.load(f)
    assert data["browser_specific_settings"]["gecko"]["id"] == "test-meet@domain.com"


def test_web_ext_lint_passes(tmp_path):
    staging = tmp_path / "staging"
    prepare_firefox_staging(
        extension_dir=Path(__file__).resolve().parent.parent / "extension",
        staging_dir=staging,
        addon_id="test-meet@domain.com"
    )
    ok, output = run_web_ext_lint(staging)
    assert ok is True
    assert "errors          0" in output


def test_sign_dry_run_and_lint_only(tmp_path):
    lint_res = sign_firefox_addon(
        output_dir=tmp_path,
        lint_only=True
    )
    assert lint_res["status"] == "lint_passed"

    dry_res = sign_firefox_addon(
        output_dir=tmp_path,
        dry_run=True,
        api_key="user:123",
        api_secret="sec_456"
    )
    assert dry_res["status"] == "dry_run"
    assert "web-ext sign" in dry_res["command"]
    assert dry_res["credentials_present"] is True


def test_missing_credentials_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("WEB_EXT_API_KEY", raising=False)
    monkeypatch.delenv("WEB_EXT_API_SECRET", raising=False)
    monkeypatch.delenv("AMO_JWT_ISSUER", raising=False)
    monkeypatch.delenv("AMO_JWT_SECRET", raising=False)

    with pytest.raises(ValueError, match="Credenciales de Mozilla AMO ausentes"):
        sign_firefox_addon(output_dir=tmp_path, dry_run=False)
