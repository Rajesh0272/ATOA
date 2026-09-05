from types import SimpleNamespace

from app.llm.client import LLMClient


def test_sarvam_json_call_uses_supported_arguments():
    captured = {}

    class FakeCompletions:
        def __call__(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content='{"ok": true}'),
                        finish_reason="stop",
                    )
                ]
            )

    client = LLMClient.__new__(LLMClient)
    client.provider = "sarvam"
    client.client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions())
    )

    result = client.json_call(
        system="Return JSON.",
        user="{}",
        schema_hint='{"ok": "boolean"}',
    )

    assert result == {"ok": True}
    assert "response_format" not in captured
