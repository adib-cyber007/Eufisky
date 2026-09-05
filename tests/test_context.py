"""Plain-English Guardian evidence summaries."""

import pytest

from app.session.context import guardian_context


def make(*families):
    return [{"family": family, "speaker": "caller", "phrase": family, "t_ms": 1} for family in families]


@pytest.mark.parametrize(("families", "phrase"), [
    (("pii_request", "authority_impersonation"), "asked for your Medicare number while claiming to be from Medicare"),
    (("payment_method",), "asked you to buy gift cards"),
    (("family_emergency",), "said a family member is in trouble and needs money"),
    (("remote_access",), "asked to get onto your computer"),
    (("pii_disclosure",), "you had started reading out numbers"),
])
def test_signal_plain_english(families, phrase) -> None:
    context = guardian_context(make(*families), caller_name="Michael", claim="Medicare", senior_name="Margaret", family_name="Sarah")
    assert context["trigger_plain"] == phrase


def test_requests_and_disclosure_summary() -> None:
    context = guardian_context(make("pii_request", "remote_access", "pii_disclosure"), caller_name="M", claim="bank", senior_name="Margaret", family_name="Sarah")
    assert context["requests"] == "personal or account numbers, access to your computer"
    assert context["disclosed"] == "started reading digits"
