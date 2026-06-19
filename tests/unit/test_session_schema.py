from evozeus_runtime.sessions.schema import SessionEnvelope, SessionEvent


def test_session_envelope_defaults_schema_version():
    envelope = SessionEnvelope(
        session_id="s1",
        provider="codex",
        source_ref="session.jsonl",
        events=[SessionEvent(event_id="e1", role="user", content="hello")],
    )

    assert envelope.schema_version == "session_envelope.v0"
    assert envelope.events[0].event_id == "e1"

