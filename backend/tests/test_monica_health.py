"""Monica health agent — food logging and routing."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from src.agents.health import (
    classify_health_intent,
    handle_log_food,
    handle_nutrition_status,
)
from src.services import food_log as fl
from src.storage.models import FoodEntry


def test_classify_food_log() -> None:
    assert classify_health_intent("I had oatmeal with berries for breakfast") == "log_food"


def test_classify_workout() -> None:
    assert classify_health_intent("I did 30 min yoga this morning") == "log_workout"


def test_classify_nutrition_status() -> None:
    assert classify_health_intent("how am I doing with my nutrition this week?") == "nutrition_status"


def test_classify_general_chat() -> None:
    assert classify_health_intent("is intermittent fasting good for me?") == "chat"


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.mark.asyncio
async def test_handle_log_food_with_usda(session: Session) -> None:
    usda_hit = {
        "description": "Oatmeal, cooked",
        "calories": 150.0,
        "protein_g": 5.0,
        "carbs_g": 27.0,
        "fat_g": 3.0,
        "serving": "cup",
    }
    with (
        patch("src.agents.health.get_settings") as mock_settings,
        patch("src.agents.health.search_food", AsyncMock(return_value=usda_hit)),
        patch("src.agents.health.fl.mirror_day", AsyncMock(return_value="02-Health/Food/2026-06-02.md")),
    ):
        mock_settings.return_value.usda_api_key = "test-key"
        result = await handle_log_food("I had oatmeal with berries for breakfast", session)

    assert "Logged" in result["reply"]
    assert result["obsidian_path"]
    entries = session.exec(select(FoodEntry)).all()
    assert len(entries) == 1
    assert entries[0].calories == 150.0


@pytest.mark.asyncio
async def test_nutrition_status_empty(session: Session) -> None:
    result = await handle_nutrition_status(session)
    assert "No meals logged" in result["reply"]


@pytest.mark.asyncio
async def test_nutrition_status_with_entries(session: Session) -> None:
    fl.add(session, description="Eggs", calories=200, protein_g=14)
    result = await handle_nutrition_status(session)
    assert "Your nutrition this week" in result["reply"]
    assert "200" in result["reply"] or "Today" in result["reply"]
