from pathlib import Path

import pytest

from starlette.testclient import TestClient

from serving.serv import Serv


def write_yaml(tmpdir: Path, content: str, env: str = "dev") -> Path:
    p = tmpdir / f"serving.{env}.yaml"
    p.write_text(content)
    return p


def test_static_serves_assets_in_dev(tmp_path: Path):
    # Prepare static directory and file
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "app.txt").write_text("hello static")

    yaml = f"""
environment: dev

auth:
  credential_provider: serving.auth:HMACCredentialProvider
  config:
    csrf_secret: test-secret

static:
  mount: /static
  directory: {static_dir.name}
  name: static
  # serve omitted -> defaults true in dev
"""
    write_yaml(tmp_path, yaml)

    serv = Serv(working_directory=tmp_path, environment="dev")
    client = TestClient(serv.app)

    r = client.get("/static/app.txt")
    assert r.status_code == 200
    assert r.text == "hello static"


def test_missing_static_asset_returns_404_status(tmp_path: Path, caplog):
    # Static dir exists but file does not
    static_dir = tmp_path / "static"
    static_dir.mkdir()

    yaml = f"""
environment: dev

auth:
  credential_provider: serving.auth:HMACCredentialProvider
  config:
    csrf_secret: test-secret

static:
  mount: /assets
  directory: {static_dir.name}
  name: static
"""
    write_yaml(tmp_path, yaml)

    serv = Serv(working_directory=tmp_path, environment="dev")
    client = TestClient(serv.app)

    caplog.set_level("WARNING")
    r = client.get("/assets/missing.txt")
    # Expect a proper 404 status and a log entry about missing static file
    assert r.status_code == 404
    assert any("Static asset not found" in rec.message for rec in caplog.records)


def test_invalid_static_shape_raises(tmp_path: Path):
    # Invalid: list instead of mapping
    yaml = """
environment: dev

auth:
  credential_provider: serving.auth:HMACCredentialProvider
  config:
    csrf_secret: test-secret

static:
  - mount: /static
    directory: static
"""
    write_yaml(tmp_path, yaml)

    with pytest.raises(Exception):
        Serv(working_directory=tmp_path, environment="dev")
