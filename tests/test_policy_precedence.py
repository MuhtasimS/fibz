from fibz_bot.policy.precedence import resolve_instructions, build_prompt_text

def test_precedence():
    core = {"style":{"tone":"formal","length":"concise"}, "safety":{"share":"same_channel"}}
    user = {"style":{"length":"detailed"}}
    server = {"style":{"tone":"casual","emoji":True}}
    merged = resolve_instructions(core, user, server)
    assert merged["style"]["tone"] == "formal"
    assert merged["style"]["length"] == "detailed"
    assert merged["style"]["emoji"] is True
    assert merged["safety"]["share"] == "same_channel"

def test_prompt_build():
    text = build_prompt_text("CORE", "USER", "SERVER")
    assert text.index("CORE") < text.index("USER") < text.index("SERVER")
