"""Goal-delivery mode (SIGNAL-E2E-001) — pins koru's goal.py contract from the scheduler side:
success is measured by a real end-to-end ACTION (or an honest single-input waiting_human),
NOT by counting closed code tickets. The scheduler must freeze unrelated refactor/self-evolution
while a delivery goal is active, and never generate new code tickets when the only gap is human.
"""
from __future__ import annotations

import pytest

from urirun_connector_work import goal


@pytest.fixture(autouse=True)
def _goal_env(tmp_path, monkeypatch):
    monkeypatch.setattr(goal, "_GOAL_FILE", tmp_path / "current-goal.json")
    monkeypatch.setenv("CURRENT_GOAL", "signal.message.send")


def test_goal_mode_freezes_unrelated_work():
    tickets = [
        {"id": "SIG", "name": "signal account status", "labels": ["goal:signal.message.send"]},
        {"id": "REF", "name": "refactor dashboard scheduler", "labels": ["refactor"]},
        {"id": "EVO", "name": "[EWOLUCJA] provenance", "labels": ["evolution"]},
    ]
    relevant, frozen = goal.goal_filter(tickets)
    assert [t["id"] for t in relevant] == ["SIG"]          # only goal-related is workable
    assert {t["id"] for t in frozen} == {"REF", "EVO"}      # refactor + self-evolution frozen
    assert goal.freeze_self_evolution() is True


def test_no_current_goal_means_normal_scheduler(monkeypatch):
    monkeypatch.delenv("CURRENT_GOAL", raising=False)
    tickets = [{"id": "REF", "name": "refactor", "labels": ["refactor"]}]
    relevant, frozen = goal.goal_filter(tickets)
    assert not frozen and [t["id"] for t in relevant] == ["REF"]  # code-improvement mode: nothing frozen


def test_delivery_without_channel_is_honest_waiting_human(monkeypatch):
    # brak kanału (ani host signal-cli ani lenovo Signal Desktop)
    monkeypatch.setattr(goal, "signal_channel", lambda node="lenovo": {"channel": "none", "ready": False})
    d = goal.deliver_signal(recipient="+48XXXXXXXXX", message="test ifuri")
    assert d["decision"] == "waiting_human"
    assert d["no_new_code_tickets_created"] is True         # KLUCZOWE: brak mielenia kodu
    assert d["missing_only"]                                 # jeden nazwany brak


def test_channel_ready_blocker_is_send_approval_not_link(monkeypatch):
    # KOREKTA: kanał gotowy (Signal Desktop na lenovo) → brama to ZGODA na wysyłkę, NIE link/QR
    monkeypatch.setattr(goal, "signal_channel", lambda node="lenovo": {"channel": "signal-gui-kvm", "node": "lenovo", "ready": True})
    d = goal.deliver_signal(recipient="+48111", message="test")  # bez approved i bez delegacji
    assert d["decision"] == "waiting_human" and d["reason"] == "send_needs_approval"
    assert d["no_new_code_tickets_created"] is True


def test_channel_ready_no_recipient_asks_for_it(monkeypatch):
    monkeypatch.setattr(goal, "signal_channel", lambda node="lenovo": {"channel": "signal-gui-kvm", "ready": True})
    d = goal.deliver_signal()  # brak recipient/treści
    assert d["reason"] == "need_recipient_and_text" and d["no_new_code_tickets_created"] is True


def test_call_llm_with_oqllm_docker(monkeypatch):
    """Verify unified LLM call through local OQLLM Docker instance."""
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:11437/health", timeout=1.0) as resp:
            if resp.status != 200:
                pytest.skip("OQLLM Docker not healthy")
    except Exception:
        pytest.skip("OQLLM Docker not reachable on 11437")

    monkeypatch.setenv("URIRUN_LLM_API_BASE", "http://127.0.0.1:11437/v1")
    monkeypatch.setenv("URIRUN_LLM_API_KEY", "oqllm_live_loopback_root")

    res = goal._llm_completion(
        prompt="proc://dockuri/ops/container/list",
        model="oqlos/system-one-router",
        max_tokens=200,
    )
    assert res.get("ok") is True
    assert "proc://dockuri/ops/container/list" in res.get("content", "")



def test_gateway_credentials_are_opt_in(monkeypatch):
    for var in ("URIRUN_LLM_API_BASE", "URIRUN_LLM_API_KEY", "OQLLM_API_KEY", "OPENAI_API_BASE", "OPENROUTER_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-must-not-leak")
    model, kw = goal._gateway_call("openrouter/z-ai/glm-5.3")
    assert model == "openrouter/z-ai/glm-5.3" and kw == {}

    # pre-existing transport override keeps its original semantics (no key, no renaming)
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://proxy.example/v1")
    model, kw = goal._gateway_call("anthropic/claude")
    assert model == "anthropic/claude" and kw == {"api_base": "https://proxy.example/v1"}

    monkeypatch.setenv("URIRUN_LLM_API_BASE", "http://127.0.0.1:11437/v1")
    monkeypatch.setenv("OQLLM_API_KEY", "oqllm-key")
    model, kw = goal._gateway_call("oqlos/system-one-router")
    assert model == "openai/oqlos/system-one-router"
    assert kw == {"api_base": "http://127.0.0.1:11437/v1", "api_key": "oqllm-key"}
