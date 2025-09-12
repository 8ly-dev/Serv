import tempfile
from pathlib import Path

from serving.serv import Serv


def test_session_provider_wires_after_auth(tmp_path: Path):
    yaml = """
environment: dev

auth:
  credential_provider: serving.auth:TimedHMACCredentialProvider
  config:
    csrf_secret: change-me-please-this-is-long
    csrf_ttl_seconds: 60

session:
  session_provider: serving.session:InMemorySessionProvider
  config: {}
"""
    (tmp_path / "serving.dev.yaml").write_text(yaml)

    serv = Serv(working_directory=tmp_path, environment="dev")

    # Should be able to create a session token via provider
    from serving.session import SessionProvider as _SP
    sp = serv.container.get(_SP)
    token = serv.container.call(sp.create_session)
    assert isinstance(token, str) and token
