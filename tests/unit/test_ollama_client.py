from ai_engine.llm.ollama_client import strip_think


def test_strip_think_removes_reasoning_block():
    raw = "<think>je réfléchis...</think>\n{\"a\": 1}"
    assert strip_think(raw) == '{"a": 1}'


def test_strip_think_leaves_normal_text():
    assert strip_think("Bonjour") == "Bonjour"