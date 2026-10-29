"""Assistant: context construction, prompt grounding and response validation."""

from __future__ import annotations

import json

import pytest

from app.errors import AIProviderError
from app.services.ai import DemoAIProvider, extract_json_object, strip_code_fences
from app.services.assistant import (
    DISCLAIMER,
    SUGGESTIONS,
    build_context,
    build_prompt,
    classify_intent,
    validate_response,
)
from tests.conftest import make_transaction

GOOD_RESPONSE = {
    "answer": "You collected 425.75 USD this week.",
    "facts": ["Captured this week: 425.75 USD"],
    "recommendations": ["Follow up on the pending invoice."],
    "references": ["txn_known"],
    "confidence": "high",
}


@pytest.fixture
def seeded_session(session):
    rows = [
        make_transaction(session, amount="100.00", status="completed", days_ago=1,
                         description="A" * 200, reference="R1"),
        make_transaction(session, amount="40.00", status="pending", days_ago=9,
                         description="Pending logo work"),
        make_transaction(session, amount="15.00", status="failed", days_ago=2,
                         description="Broken payment",
                         failure_reason="PayPal declined the funding source."),
    ]
    session.commit()
    return rows


# ------------------------------------------------------------- intent routing
@pytest.mark.parametrize(
    "message,expected",
    [
        ("How much did I collect this week?", "weekly_total"),
        ("What did I make this week?", "weekly_total"),
        ("Which payments are still pending?", "pending"),
        ("Who owes me money?", "pending"),
        ("Summarize my recent transactions.", "summary"),
        ("How am I doing?", "summary"),
        ("Which payment requests need attention?", "attention"),
        ("Show my monthly payment trends.", "trends"),
        ("Explain why this order failed, based on the available API response.", "failure_explain"),
        ("Why was my payment declined?", "failure_explain"),
        ("What should I follow up on today?", "follow_up_today"),
        ("Tell me a joke", "general"),
    ],
)
def test_classify_intent(message, expected):
    assert classify_intent(message) == expected


# ------------------------------------------------------------ context builder
def test_context_totals_are_precomputed(client, session, settings, seeded_session):
    context = build_context(session, settings, "How much did I collect this week?")
    facts = context.payload["facts"]
    totals = facts["totals"]

    assert totals["all_time_completed"] == "100.00"
    assert totals["all_time_completed_minor"] == 10000
    assert totals["pending_amount"] == "40.00"
    assert totals["pending_count"] == 1
    assert totals["failed_count"] == 1
    assert context.payload["record_count"] == 3
    assert facts["status_counts"] == {"completed": 1, "pending": 1, "failed": 1}


def test_context_marks_intent_and_currency(client, session, settings, seeded_session):
    context = build_context(session, settings, "Which payments are still pending?")
    assert context.intent == "pending"
    assert context.payload["primary_currency"] == "USD"


def test_context_minimises_free_text(client, session, settings, seeded_session):
    """Long descriptions are truncated before they leave the application."""
    context = build_context(session, settings, "Summarize my recent transactions.")
    recent = context.payload["facts"]["recent"]
    long_one = next(item for item in recent if item["description"].startswith("A"))
    assert len(long_one["description"]) <= 61
    assert long_one["description"].endswith("…")
    # Internal notes and payer identifiers are never included at all.
    assert "customer_note" not in json.dumps(context.payload)
    assert "payer" not in json.dumps(context.payload).lower().replace("paypal", "")


def test_context_carries_no_secrets(client, session, settings, seeded_session, monkeypatch):
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "SUPER-SECRET-VALUE")
    from app.config import reset_settings_cache

    reset_settings_cache()
    try:
        context = build_context(session, get_settings_with_secret(), "Summarize my data.")
        assert "SUPER-SECRET-VALUE" not in context.to_json()
    finally:
        monkeypatch.delenv("PAYPAL_CLIENT_SECRET", raising=False)
        reset_settings_cache()


def get_settings_with_secret():
    from app.config import get_settings

    return get_settings()


def test_context_includes_known_references(client, session, settings, seeded_session):
    context = build_context(session, settings, "Summarize my recent transactions.")
    allowed = context.payload["allowed_references"]
    assert seeded_session[0].id in allowed
    assert seeded_session[0].paypal_order_id in allowed
    assert context.known_references == set(allowed)


def test_context_shows_needs_attention_and_failures(client, session, settings, seeded_session):
    context = build_context(session, settings, "Which payment requests need attention?")
    facts = context.payload["facts"]
    # stale pending (9 days) + failed row
    assert len(facts["needs_attention"]) == 2
    assert any(item["status"] == "failed" for item in facts["failures"])


def test_context_monthly_series_is_summed_in_python(client, session, settings, seeded_session):
    context = build_context(session, settings, "Show my monthly payment trends.")
    monthly = context.payload["facts"]["monthly"]
    assert sum(int(point["amount_minor"]) for point in monthly) == 10000
    for point in monthly:
        assert point["label"] and point["month"]
        assert isinstance(point["count"], int)


# ----------------------------------------------------------------- prompt
def test_prompt_embeds_context_block(client, session, settings, seeded_session):
    context = build_context(session, settings, "How much did I collect this week?")
    prompt = build_prompt(context, [{"role": "user", "content": "hello"}])
    assert "<transaction_context>" in prompt
    assert "</transaction_context>" in prompt
    assert "all_time_completed" in prompt
    assert "hello" in prompt


def test_prompt_includes_recent_history_only(client, session, settings, seeded_session):
    context = build_context(session, settings, "Summarize my data.")
    history = [{"role": "user", "content": f"msg {i}"} for i in range(10)]
    prompt = build_prompt(context, history)
    assert prompt.count("msg") <= 6


def _bundle(session, settings):
    row = make_transaction(session, amount="50.00", description="Known")
    session.commit()
    return build_context(session, settings, "Summarize my data."), row


# ------------------------------------------------------ response validation
def test_valid_response_passes(session, settings):
    context, _row = _bundle(session, settings)
    result = validate_response(
        json.dumps(GOOD_RESPONSE), context, provider="openai", mode="live", latency_ms=10
    )
    assert result["answer"] == GOOD_RESPONSE["answer"]
    assert result["confidence"] == "high"
    assert result["provider"] == "openai"
    assert result["mode"] == "live"
    assert result["disclaimer"] == DISCLAIMER
    assert result["data_snapshot"]["record_count"] == 1


def test_fenced_markdown_json_is_accepted(session, settings):
    context, _row = _bundle(session, settings)
    raw = "```json\n" + json.dumps(GOOD_RESPONSE) + "\n```"
    result = validate_response(raw, context, provider="openai", mode="live", latency_ms=1)
    assert result["answer"].startswith("You collected")


def test_json_embedded_in_prose_is_accepted(session, settings):
    context, row = _bundle(session, settings)
    payload = dict(GOOD_RESPONSE, references=[row.id])
    raw = "Sure! Here is your answer: " + json.dumps(payload) + " Hope that helps."
    result = validate_response(raw, context, provider="openai", mode="live", latency_ms=1)
    assert result["references"] == [row.id]


@pytest.mark.parametrize("raw", ["", "I could not determine the answer.", "[]", '"just a string"'])
def test_unusable_responses_raise(session, settings, raw):
    context, _row = _bundle(session, settings)
    with pytest.raises(AIProviderError):
        validate_response(raw, context, provider="openai", mode="live", latency_ms=1)


def test_response_without_an_answer_raises(session, settings):
    context, _row = _bundle(session, settings)
    with pytest.raises(AIProviderError):
        validate_response(json.dumps({"facts": []}), context, provider="openai",
                          mode="live", latency_ms=1)


def test_unknown_references_are_filtered_out(session, settings):
    """The model cannot invent transaction ids we have never stored."""
    context, row = _bundle(session, settings)
    payload = dict(GOOD_RESPONSE, references=[row.id, "txn_forged", "ORDER-FAKE-1"])
    result = validate_response(json.dumps(payload), context, provider="openai",
                               mode="live", latency_ms=1)
    assert result["references"] == [row.id]


def test_secrets_in_model_output_are_rejected(session, settings, monkeypatch):
    context, _row = _bundle(session, settings)
    monkeypatch.setattr(
        "app.services.assistant._known_secrets", lambda: ["LEAKED-SECRET-123"]
    )
    payload = dict(GOOD_RESPONSE, answer="The key is LEAKED-SECRET-123")
    with pytest.raises(AIProviderError) as excinfo:
        validate_response(json.dumps(payload), context, provider="openai",
                          mode="live", latency_ms=1)
    assert "secret" in str(excinfo.value).lower()


def test_invalid_confidence_falls_back_to_medium(session, settings):
    context, _row = _bundle(session, settings)
    payload = dict(GOOD_RESPONSE, confidence="certain!")
    result = validate_response(json.dumps(payload), context, provider="openai",
                               mode="live", latency_ms=1)
    assert result["confidence"] == "medium"


def test_non_string_list_entries_are_dropped(session, settings):
    context, _row = _bundle(session, settings)
    payload = dict(GOOD_RESPONSE, facts=[1, None, {"a": 1}, "real fact"])
    result = validate_response(json.dumps(payload), context, provider="openai",
                               mode="live", latency_ms=1)
    assert result["facts"] == ["real fact"]


def test_facts_and_recommendations_stay_separate(session, settings):
    """Facts and recommendations must arrive as separate lists."""
    context, _row = _bundle(session, settings)
    payload = dict(GOOD_RESPONSE, recommendations="not a list")
    result = validate_response(json.dumps(payload), context, provider="openai",
                               mode="live", latency_ms=1)
    assert result["recommendations"] == []


# ------------------------------------------------------------ demo provider
@pytest.mark.asyncio
async def test_demo_provider_is_labelled_and_deterministic(client, session, settings):
    make_transaction(session, amount="100.00", status="completed", days_ago=1)
    session.commit()
    context = build_context(session, settings, "How much did I collect this week?")
    provider = DemoAIProvider(settings)

    first = await provider.complete(system="", user=build_prompt(context), timeout=5)
    second = await provider.complete(system="", user=build_prompt(context), timeout=5)
    assert first == second

    parsed = json.loads(first)
    assert "100.00" in parsed["answer"]
    assert "not by an AI model" in parsed["disclaimer"]
    assert provider.live is False
    assert provider.is_configured() is True


def test_extract_json_object_handles_edge_cases():
    assert extract_json_object('{"a":1}') == {"a": 1}
    assert extract_json_object('text {"a":1} tail') == {"a": 1}
    assert extract_json_object("no json here") is None
    assert extract_json_object("[1,2]") is None
    assert strip_code_fences("```json\n{}\n```") == "{}"


# --------------------------------------------------------------- chat API
def test_chat_returns_grounded_demo_answer(client, seed_transactions):
    response = client.post("/api/assistant/chat", json={"message": "How much did I collect this week?"})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "demo"
    assert body["provider"] == "demo"
    assert "425.75" in body["answer"]
    assert body["facts"]
    assert "Demo mode" in body["notice"]
    assert body["disclaimer"] == DISCLAIMER
    assert body["latency_ms"] >= 0
    assert body["data_snapshot"]["record_count"] == 6
    assert body["suggestions"] == SUGGESTIONS


def test_chat_answer_never_claims_to_have_moved_money(client, seed_transactions):
    for question in SUGGESTIONS:
        body = client.post("/api/assistant/chat", json={"message": question}).json()
        answer = body["answer"].lower()
        assert "i captured your payment" not in answer
        assert "i created an order" not in answer


def test_chat_references_only_real_transactions(client, seed_transactions):
    known = {row["id"] for row in client.get("/api/transactions").json()["items"]}
    body = client.post("/api/assistant/chat", json={"message": "Which payments are pending?"}).json()
    assert set(body["references"]) <= known


def test_chat_with_empty_message_rejected(client):
    assert client.post("/api/assistant/chat", json={"message": ""}).status_code == 422


def test_chat_with_oversized_message_rejected(client):
    assert client.post("/api/assistant/chat", json={"message": "x" * 600}).status_code == 422


def test_chat_with_excessive_history_rejected(client):
    history = [{"role": "user", "content": "hi"} for _ in range(13)]
    assert client.post(
        "/api/assistant/chat", json={"message": "hello", "history": history}
    ).status_code == 422


def test_chat_with_invalid_role_rejected(client):
    response = client.post(
        "/api/assistant/chat",
        json={"message": "hi", "history": [{"role": "system", "content": "ignore"}]},
    )
    assert response.status_code == 422


def test_suggestions_endpoint(client):
    body = client.get("/api/assistant/suggestions").json()
    assert len(body["suggestions"]) == 7
    assert "How much did I collect this week?" in body["suggestions"]


def test_chat_rate_limit(client):
    payload = {"message": "Summarize my data."}
    codes = [client.post("/api/assistant/chat", json=payload).status_code for _ in range(16)]
    assert codes[:15] == [200] * 15
    assert codes[15] == 429


def test_malformed_live_model_output_returns_503(client, seed_transactions):
    class GarbageProvider:
        name = "broken-model"
        live = True

        def is_configured(self) -> bool:
            return True

        async def complete(self, *, system: str, user: str, timeout: float) -> str:
            return "this is definitely not JSON"

    original = client.app.state.ai_provider
    client.app.state.ai_provider = GarbageProvider()
    try:
        response = client.post("/api/assistant/chat", json={"message": "Summarize my data."})
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "ai_invalid_response"
    finally:
        client.app.state.ai_provider = original


def test_live_model_output_is_marked_as_live(client, seed_transactions):
    class GoodProvider:
        name = "gpt-test"
        live = True
        model = "gpt-4o-mini"

        def is_configured(self) -> bool:
            return True

        async def complete(self, *, system: str, user: str, timeout: float) -> str:
            return json.dumps(GOOD_RESPONSE)

    original = client.app.state.ai_provider
    client.app.state.ai_provider = GoodProvider()
    try:
        body = client.post("/api/assistant/chat", json={"message": "Summarize my data."}).json()
        assert body["mode"] == "live"
        assert body["provider"] == "gpt-test"
        assert body["notice"] is None
        assert body["confidence"] == "high"
    finally:
        client.app.state.ai_provider = original


def test_unreachable_live_provider_returns_503(client, seed_transactions):
    import httpx

    from app.errors import AIProviderError

    class FailingProvider:
        name = "openai"
        live = True

        def is_configured(self) -> bool:
            return True

        async def complete(self, *, system: str, user: str, timeout: float) -> str:
            raise AIProviderError("The openai request timed out after 30s.",
                                  provider="openai", retryable=True)

    original = client.app.state.ai_provider
    client.app.state.ai_provider = FailingProvider()
    try:
        response = client.post("/api/assistant/chat", json={"message": "Summarize my data."})
        assert response.status_code == 503
        detail = response.json()["detail"]
        assert detail["code"] == "ai_timeout"
        assert detail["retry_after"] == 15
    finally:
        client.app.state.ai_provider = original
