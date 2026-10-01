"""Load Career/Profile notes for Rachel. Never writes Profile/ or Context/."""
from __future__ import annotations

from src.integrations import ObsidianClient

PROFILE_DIR = "Career/Profile"
PROFILE_FILES = ("background.md", "skills.md", "goals.md", "paths.md")
CONTEXT_PATH = "Context/career.md"
MAX_FILE_CHARS = 6000

_TEMPLATE_MARKERS = ("status: template", "<!-- fill this in -->", "[your ")


def is_template(content: str) -> bool:
    lowered = content.lower()
    return any(m in lowered for m in _TEMPLATE_MARKERS)


def _clip(text: str) -> str:
    text = text.strip()
    if len(text) <= MAX_FILE_CHARS:
        return text
    return text[: MAX_FILE_CHARS - 1] + "…"


async def load_career_context() -> tuple[str, bool]:
    """Return (prompt block, profile_is_usable).

    `profile_is_usable` is False when every file is missing or still a template.
    """
    sections: list[str] = []
    usable = False

    async with ObsidianClient() as obs:
        notes = await obs.read_markdown_folder(PROFILE_DIR)
        try:
            context_md = await obs.read_note(CONTEXT_PATH)
        except Exception:
            context_md = ""

    for filename in PROFILE_FILES:
        body = notes.get(filename, "").strip()
        heading = filename.replace(".md", "").title()
        if not body:
            sections.append(f"### {heading}\n_(missing — {PROFILE_DIR}/{filename})_")
            continue
        if not is_template(body):
            usable = True
        sections.append(f"### {heading} (`{PROFILE_DIR}/{filename}`)\n{_clip(body)}")

    if context_md.strip() and not is_template(context_md):
        usable = True
        sections.append(f"### Classifier context (`{CONTEXT_PATH}`)\n{_clip(context_md)}")

    return "\n\n".join(sections), usable
