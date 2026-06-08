"""Save article/link intent detection."""
from __future__ import annotations

from src.agents.knowledge import (
    classify_sub_intent,
    is_bare_url_save,
    is_contextual_save_request,
    is_save_command,
    is_save_link_request,
)


def test_save_article_phrases() -> None:
    assert is_save_command("save this article")
    assert is_save_command("add this link to my reading list")
    assert is_save_command("bookmark this blog post")
    assert is_save_command("keep this url")


def test_bare_url_save() -> None:
    assert is_bare_url_save("https://openai.com/blog/chatgpt")
    assert is_bare_url_save("Found this interesting https://example.com/article")
    assert not is_bare_url_save("what is this about https://example.com/article?")
    assert not is_bare_url_save("explain https://example.com/article to me")


def test_contextual_save_from_history() -> None:
    history = [
        {"role": "assistant", "content": "Check out https://openai.com/blog/new-model"},
    ]
    assert is_contextual_save_request("save this article to my reading list", history)
    assert classify_sub_intent("add this to my reading list", history=history) == "save"


def test_save_link_before_chat() -> None:
    assert classify_sub_intent("save me from this meeting") == "chat"
    assert classify_sub_intent("https://openai.com/blog") == "save"
    assert is_save_link_request("https://openai.com/blog")
