from fibz_bot.utils.metrics import metrics, record_model_choice, record_tool_call, record_command

def test_metrics_inc():
    record_model_choice("flash")
    record_model_choice("pro")
    record_tool_call("web_search")
    record_command("ask")
    snap = metrics.snapshot()
    assert snap["model_choice.flash"] >= 1
    assert snap["model_choice.pro"] >= 1
    assert snap["tool.web_search"] >= 1
    assert snap["cmd.ask"] >= 1
    assert "uptime_seconds" in snap
