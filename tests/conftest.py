import pytest


@pytest.fixture(autouse=True)
def explicit_test_delegation(tmp_path, monkeypatch):
    """Tests declare delegated authority explicitly; the runtime default grants none."""
    from urirun_connector_human_twin import core as twin

    config = tmp_path / "delegations.yaml"
    config.write_text(
        """
delegations:
  - id: publish-generated-connectors
    allow:
      actions: [pypi.publish]
      scope: {org: urirun-connectors, package_prefix: urirun-connector-}
      conditions: {tests_passed: true, smoke_passed: true, no_secrets_detected: true, destructive: false, version_bump_valid: true}
      max_risk: medium
    expires_at: '2999-01-01T00:00:00+00:00'
twin_never: [credential.export, exfiltrate_secrets]
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(twin, "_YAML", config)
