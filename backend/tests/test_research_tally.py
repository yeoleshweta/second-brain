from datetime import date
from pathlib import Path

from src.services.research_tally import count_daily_log_lines, count_unsorted_for_day, tally_for_day


def test_count_daily_log_lines_only_under_log(tmp_path: Path) -> None:
    note = tmp_path / "2026-10-09.md"
    note.write_text(
        "# 2026-10-09\n\n## Log\n"
        "- 08:14 🍽 **food** :: eggs [src:: user]\n"
        "- 09:00 ✅ **task** :: meeting [src:: user]\n"
        "## Notes\n- 10:00 not a log line in notes\n",
        encoding="utf-8",
    )
    assert count_daily_log_lines(note) == 2


def test_count_unsorted_prefix(tmp_path: Path) -> None:
    d = tmp_path
    (d / "2026-10-09-120000.md").write_text("x", encoding="utf-8")
    (d / "2026-10-08-120000.md").write_text("x", encoding="utf-8")
    (d / "README.md").write_text("x", encoding="utf-8")
    assert count_unsorted_for_day(d, date(2026, 10, 9)) == 1


def test_tally_for_day_missing_files(tmp_path: Path) -> None:
    log_n, unsorted_n = tally_for_day(tmp_path, date(2026, 10, 9))
    assert log_n == 0
    assert unsorted_n == 0
