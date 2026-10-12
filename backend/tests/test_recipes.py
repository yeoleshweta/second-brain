from src.services.recipes import Recipe, asks_for_recipes, format_recipe_reply, parse_recipe_file


def test_parse_personal_and_youtube() -> None:
    text = """
## Log

- 09:10 🥘 **recipe** :: Dal: boil lentils, add salt [src:: user]
- 11:02 🥘 **recipe** :: Shared from YouTube: https://youtu.be/abc123 — Crispy chicken [src:: user]
"""
    items = parse_recipe_file("2026-10-11.md", text)
    assert len(items) == 2
    assert items[0].kind == "personal"
    assert "lentils" in items[0].body
    assert items[1].kind == "youtube"
    assert items[1].url == "https://youtu.be/abc123"
    assert items[1].title == "Crispy chicken"


def test_fetch_named_recipe() -> None:
    recipes = [
        Recipe(
            "2026-10-11",
            "09:10",
            "Dal: boil lentils",
            "00-Inbox/Void/2026-10-11.md",
            "",
            "Dal: boil lentils",
            "personal",
        ),
        Recipe(
            "2026-10-11",
            "11:02",
            "https://youtu.be/abc123 — Crispy chicken",
            "00-Inbox/Void/2026-10-11.md",
            "https://youtu.be/abc123",
            "Crispy chicken",
            "youtube",
        ),
    ]
    reply = format_recipe_reply("what's my dal recipe", recipes)
    assert "lentils" in reply
    assert "Crispy chicken" not in reply
    missing = format_recipe_reply("recipe for sushi", recipes)
    assert "don't have" in missing


def test_refile_last_unsorted_line() -> None:
    from src.integrations.obsidian import refile_last_unsorted, refile_request

    text = "- 09:10 unsorted (no type matched) :: hello there [src:: user]\n"
    updated = refile_last_unsorted(text, "health")
    assert updated is not None
    assert "**health**" in updated
    assert "unsorted" not in updated
    assert refile_request("file the last note as health") == "health"
    assert asks_for_recipes("show me my recipes")
    assert not asks_for_recipes("remember this recipe: boil lentils")
