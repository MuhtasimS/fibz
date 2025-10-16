from fibz_bot.policy.consent import classify_info, ConsentDecision, can_share

def test_classify():
    assert classify_info({"tags":["private"]}) == ConsentDecision.PRIVATE
    assert classify_info({"email":"a@b.com"}) == ConsentDecision.CONSENT_REQUIRED
    assert classify_info({"title":"hi"}) == ConsentDecision.SHAREABLE

def test_share_rules():
    assert can_share("r","s",{}, same_channel=True, cross_channel_toggle=False) is True
    assert can_share("r","s",{}, same_channel=False, cross_channel_toggle=False) is False
    assert can_share("r","s",{}, same_channel=False, cross_channel_toggle=True) is True
