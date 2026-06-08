"""Book discovery links when Gutenberg has no in-app download."""
from __future__ import annotations

from urllib.parse import quote_plus

from src.integrations.oceanofpdf import OceanOfPdfMatch, oceanofpdf_search_url


def legal_discovery_links(query: str) -> list[tuple[str, str, str]]:
    """Return (label, url, note) tuples for manual legal book lookup."""
    q = quote_plus(query.strip())
    return [
        (
            "Open Library",
            f"https://openlibrary.org/search?q={q}",
            "Borrow or read scans when your library participates",
        ),
        (
            "Internet Archive",
            f"https://archive.org/search?query={q}",
            "Public-domain scans and lending when available",
        ),
        (
            "Google Books",
            f"https://www.google.com/search?tbm=bks&q={q}",
            "Preview pages and purchase options",
        ),
        (
            "WorldCat",
            f"https://www.worldcat.org/search?q={q}",
            "Find a copy at a library near you",
        ),
    ]


def build_oceanofpdf_book_item(query: str, match: OceanOfPdfMatch) -> dict:
    """Interactive card for Ocean of PDF search or direct book page."""
    display = match.title.strip() or query.strip()
    if match.is_search:
        summary = (
            f"Search Ocean of PDF for **{display}**. "
            "Tap **Open in Safari** — leaves Central Perk so you can download there."
        )
    else:
        summary = (
            f"**{display}** on Ocean of PDF. "
            "Tap **Open in Safari** to download on their site."
        )
    return {
        "id": f"oceanofpdf-{abs(hash(match.url))}",
        "gutenberg_id": None,
        "title": display,
        "authors": "Ocean of PDF",
        "summary": summary,
        "url": match.url,
        "source": "oceanofpdf",
        "kind": "ebook",
        "downloadable": False,
        "in_list": False,
        "is_search": match.is_search,
    }


def format_book_not_found_alternatives(
    query: str,
    *,
    oceanofpdf_match: OceanOfPdfMatch | None = None,
    include_ocean: bool = True,
) -> str:
    """Markdown block with next-step links for unavailable titles."""
    lines = [
        f"\n\n**No free in-app download for «{query}».** "
        "Ross checked Gutenberg, Open Library, and LibriVox.",
        "\n**Legal options:**",
    ]
    for name, url, note in legal_discovery_links(query):
        lines.append(f"- [{name}]({url}) — {note}")

    if include_ocean:
        search_url = oceanofpdf_search_url(query)
        if oceanofpdf_match and not oceanofpdf_match.is_search:
            lines.append(
                f"\n**Ocean of PDF:** "
                f"[{oceanofpdf_match.title}]({oceanofpdf_match.url}) — direct book page."
            )
        else:
            lines.append(
                f"\n**Ocean of PDF search:** "
                f"[Search for «{query}»]({oceanofpdf_match.url if oceanofpdf_match else search_url}) — "
                "fallback if web search links don't work."
            )

    lines.append(
        "\n_For newer titles, **Libby** (your library app) is often the easiest legal path._"
    )
    return "\n".join(lines)
