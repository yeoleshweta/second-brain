import pytest

from src.services.social_share import ShareRejectedError, parse_share, share_line


def test_instagram_link() -> None:
    link, label, note = parse_share(
        "https://www.instagram.com/reel/ABC123/?igsh=1",
        "a post about cognitive analysis",
    )
    assert link.startswith("https://www.instagram.com/reel/ABC123/")
    assert label == "Instagram"
    assert note == "a post about cognitive analysis"
    assert "Instagram" in share_line(link, label, note)


def test_linkedin_short_link_inside_text() -> None:
    link, label, note = parse_share(
        "",
        "Worth reading https://lnkd.in/gExample1 later",
    )
    assert link == "https://lnkd.in/gExample1"
    assert label == "LinkedIn"
    assert note == "Worth reading later"


def test_other_sites_are_refused() -> None:
    with pytest.raises(ShareRejectedError):
        parse_share("https://example.com/post", "")
