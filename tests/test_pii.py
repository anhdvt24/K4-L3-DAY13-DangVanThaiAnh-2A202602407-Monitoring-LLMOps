from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_vietnamese_national_id() -> None:
    out = scrub_text("CCCD 012345678901 bị lộ")
    assert "012345678901" not in out
    assert "REDACTED_CCCD" in out


def test_scrub_credit_card_does_not_leak_substring_to_cccd() -> None:
    # Nếu pattern CCCD chạy trước credit_card, "111111111111" sẽ bị match thành CCCD,
    # khiến credit_card không còn match 16 số nữa.
    out = scrub_text("Card 4111 1111 1111 1111 expired")
    assert "4111 1111 1111 1111" not in out
    assert "REDACTED_CREDIT_CARD" in out
    # Không được để lại một đoạn 12 số nguyên văn (chứng tỏ credit_card match trước CCCD)
    import re
    leaked_substrings = re.findall(r"(?<!\d)\d{12}(?!\d)", out)
    assert leaked_substrings == [], f"CCCD leak trong: {out}"
