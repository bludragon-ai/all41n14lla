"""PII scrub regression tests — every class must bite, plain text must not."""

from all41n14lla.redact import redact


def test_all_classes_bite_in_one_sample():
    out = redact("call (415) 555-0132 or me@example.com, card 4111111111111111")
    assert "[phone]" in out and "[email]" in out and "[digits]" in out
    assert "me@example.com" not in out
    assert "555-0132" not in out
    assert "4111111111111111" not in out


def test_email_alone():
    assert redact("reach jordan@bluprintsolutions.net today") == "reach [email] today"


def test_us_phone_with_dashes():
    assert redact("dial 415-555-0132 now") == "dial [phone] now"


def test_us_phone_with_parentheses():
    assert redact("(415) 555-0132") == "[phone]"


def test_international_phone():
    out = redact("+1 415 555 0132 and +44 20 7946 0958")
    assert out.count("[phone]") == 2
    assert "555" not in out


def test_long_digit_run_masked_before_phone_shape():
    # 16-digit card must become [digits], not be partially consumed as a phone.
    assert redact("4111111111111111") == "[digits]"


def test_plain_text_survives():
    sample = "the 2026 sweep covered 4 repos on 2026-08-10"
    assert redact(sample) == sample


def test_short_numbers_left_alone():
    # 3-digit and 9-digit runs are not card/account-length; don't over-scrub.
    assert redact("page 123 of 456789012") == "page 123 of 456789012"
