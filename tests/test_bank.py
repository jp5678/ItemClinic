"""bank 모듈 테스트: 문항은행 저장/검색."""
import pytest

from itemclinic.bank import ItemBank


@pytest.fixture
def bank(tmp_path):
    return ItemBank(tmp_path / "bank.json")


class TestItemBank:
    def test_add_and_reload(self, bank, tmp_path):
        bank.add_record(
            exam_id="2026-1-midterm",
            item_id="Q5",
            stats={"difficulty": 0.42, "point_biserial": -0.14},
            severity="CRITICAL",
            text=None,
        )
        reloaded = ItemBank(tmp_path / "bank.json")
        records = reloaded.all_records()
        assert len(records) == 1
        assert records[0]["item_id"] == "Q5"

    def test_search_by_severity(self, bank):
        bank.add_record("e1", "Q1", {"difficulty": 0.5}, "OK", None)
        bank.add_record("e1", "Q2", {"difficulty": 0.1}, "CRITICAL", None)
        hits = bank.search(severity="CRITICAL")
        assert [r["item_id"] for r in hits] == ["Q2"]

    def test_search_by_difficulty_range(self, bank):
        bank.add_record("e1", "Q1", {"difficulty": 0.5}, "OK", None)
        bank.add_record("e1", "Q2", {"difficulty": 0.9}, "OK", None)
        hits = bank.search(min_difficulty=0.4, max_difficulty=0.6)
        assert [r["item_id"] for r in hits] == ["Q1"]

    def test_corrupt_file_raises_clear_error(self, tmp_path):
        path = tmp_path / "bank.json"
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(ValueError):
            ItemBank(path)
