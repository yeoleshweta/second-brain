"""USDA FoodData Central — nutrition lookup for Monica."""
from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

NUTRIENT_IDS = {
    "calories": 1008,
    "protein_g": 1003,
    "carbs_g": 1005,
    "fat_g": 1004,
}


def _nutrient_value(nutrients: list[dict[str, Any]], nutrient_id: int) -> float | None:
    for n in nutrients:
        if n.get("nutrientId") == nutrient_id or n.get("nutrientNumber") == str(nutrient_id):
            try:
                return float(n.get("value") or 0)
            except (TypeError, ValueError):
                return None
    return None


def parse_food_hit(item: dict[str, Any]) -> dict[str, float | str | None]:
    nutrients = item.get("foodNutrients") or []
    return {
        "description": str(item.get("description") or item.get("lowercaseDescription") or ""),
        "calories": _nutrient_value(nutrients, NUTRIENT_IDS["calories"]),
        "protein_g": _nutrient_value(nutrients, NUTRIENT_IDS["protein_g"]),
        "carbs_g": _nutrient_value(nutrients, NUTRIENT_IDS["carbs_g"]),
        "fat_g": _nutrient_value(nutrients, NUTRIENT_IDS["fat_g"]),
        "serving": item.get("servingSizeUnit") or "100g",
    }


async def search_food(
    query: str,
    *,
    api_key: str,
    page_size: int = 3,
) -> dict[str, float | str | None] | None:
    """Return best-match macros for a food query, or None if lookup fails."""
    q = query.strip()
    if not q or not api_key:
        return None
    params = {
        "api_key": api_key,
        "query": q,
        "pageSize": page_size,
        "dataType": ["Survey (FNDDS)", "SR Legacy", "Foundation"],
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(USDA_SEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("USDA search failed for {!r}: {}", q, exc)
        return None

    foods = data.get("foods") or []
    if not foods:
        return None
    return parse_food_hit(foods[0])
