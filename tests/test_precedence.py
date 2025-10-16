from fibz_bot.policy.precedence import build_prompt_text

def test_build_prompt_order():
    core = "CORE"
    user = "USER"
    server = "SERVER"
    out = build_prompt_text(core, user, server)
    assert "CORE" in out and "USER" in out and "SERVER" in out
    assert out.index("CORE") < out.index("USER") < out.index("SERVER")
