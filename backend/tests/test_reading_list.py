"""Reading list service unit tests (in-memory SQLite, no external deps)."""
from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine

from src.services import reading_list as rl
from src.storage.models import ItemKind, ItemStatus


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_add_and_retrieve(session):
    item = rl.add(
        session, url="https://arxiv.org/abs/2312.00752", title="Mamba Paper", kind=ItemKind.PAPER
    )
    assert item is not None
    assert item.id is not None
    assert item.status == ItemStatus.UNREAD
    assert item.progress == 0


def test_dedup_same_url(session):
    rl.add(session, url="https://arxiv.org/abs/2312.00752", title="Mamba", kind=ItemKind.PAPER)
    duplicate = rl.add(
        session, url="https://arxiv.org/abs/2312.00752", title="Mamba again", kind=ItemKind.PAPER
    )
    assert duplicate is None  # dedup


def test_add_freeform_note_no_dedup(session):
    # Notes have no URL, so two notes can coexist
    n1 = rl.add(session, title="Try BAML", kind=ItemKind.NOTE)
    n2 = rl.add(session, title="Try BAML", kind=ItemKind.NOTE)
    assert n1 is not None
    assert n2 is not None


def test_mark_read(session):
    item = rl.add(session, url="https://example.com/a", title="Article A", kind=ItemKind.URL)
    assert item is not None
    rl.mark_read(session, item)
    assert item.status == ItemStatus.READ
    assert item.finished_at is not None
    assert item.progress == 100


def test_update_progress(session):
    item = rl.add(session, url="https://example.com/b", title="Article B", kind=ItemKind.URL)
    assert item is not None
    rl.update_progress(session, item, 50)
    assert item.progress == 50
    assert item.status == ItemStatus.IN_PROGRESS

    rl.update_progress(session, item, 100)
    assert item.status == ItemStatus.READ


def test_delete(session):
    item = rl.add(session, url="https://example.com/c", title="Article C", kind=ItemKind.URL)
    assert item is not None
    rl.delete(session, item)
    assert rl.find_by_title(session, "Article C") is None


def test_stats_percent_done(session):
    rl.add(session, url="https://a.com/1", title="One", kind=ItemKind.URL)
    item2 = rl.add(session, url="https://a.com/2", title="Two", kind=ItemKind.URL)
    assert item2 is not None
    rl.mark_read(session, item2)

    s = rl.stats(session)
    assert s["total"] == 2
    assert s["read"] == 1
    assert s["percent_done"] == 50


def test_find_by_title_fuzzy(session):
    rl.add(
        session,
        url="https://example.com/mamba",
        title="Mamba: Linear-Time Sequence Modeling",
        kind=ItemKind.PAPER,
    )
    found = rl.find_by_title(session, "mamba")
    assert found is not None
    assert "Mamba" in found.title


def test_list_active_excludes_read(session):
    item1 = rl.add(session, url="https://a.com/x", title="X", kind=ItemKind.URL)
    item2 = rl.add(session, url="https://a.com/y", title="Y", kind=ItemKind.URL)
    assert item1 is not None and item2 is not None
    rl.mark_read(session, item1)

    active = rl.list_active(session)
    ids = [i.id for i in active]
    assert item2.id in ids
    assert item1.id not in ids
