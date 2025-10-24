from __future__ import annotations

import asyncio

from fibz_bot.policy.consent import classify_share_request


def test_classify_same_channel_safe():
    result = asyncio.run(
        classify_share_request(
            "What hobbies does Charlie enjoy?",
            requester_id="1",
            subject_id="2",
            guild_id="10",
            channel_id="20",
            cross_channel_enabled=True,
        )
    )
    assert result == "share_safe"


def test_classify_cross_channel_block():
    result = asyncio.run(
        classify_share_request(
            "What did they say in #admin last night?",
            requester_id="1",
            subject_id="2",
            guild_id="10",
            channel_id="21",
            cross_channel_enabled=False,
        )
    )
    assert result == "share_block"


def test_classify_private_needs_consent():
    result = asyncio.run(
        classify_share_request(
            "Can you tell me their home address?",
            requester_id="1",
            subject_id="2",
            guild_id="10",
            channel_id="21",
            cross_channel_enabled=True,
        )
    )
    assert result == "share_needs_consent"
