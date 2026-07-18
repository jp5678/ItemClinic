"""CLI 엔드투엔드 통합 테스트."""
import json

import pytest

from itemclinic.cli import main


@pytest.fixture
def sample_csv(tmp_path):
    path = tmp_path / "exam.csv"
    rows = ["student,Q1,Q2,Q3,Q4", "KEY,A,B,C,D"]
    # 12명: 상위권은 Q1~Q3 정답, Q4는 하위권만 정답(불량 문항)
    for i in range(6):
        rows.append(f"u{i},A,B,C,A")
    for i in range(6):
        rows.append(f"l{i},B,C,D,D")
    path.write_text("\n".join(rows), encoding="utf-8")
    return path


class TestAnalyzeCommand:
    def test_creates_all_outputs(self, sample_csv, tmp_path):
        out_dir = tmp_path / "out"
        code = main([
            "analyze", str(sample_csv),
            "--exam-id", "t1",
            "--out", str(out_dir),
            "--bank", str(tmp_path / "bank.json"),
            "--no-llm",
        ])
        assert code == 0
        assert (out_dir / "report.html").exists()
        assert (out_dir / "diagnosis.json").exists()
        assert (out_dir / "improve_prompt.md").exists()
        assert (tmp_path / "bank.json").exists()

    def test_diagnosis_json_structure(self, sample_csv, tmp_path):
        out_dir = tmp_path / "out"
        main([
            "analyze", str(sample_csv), "--out", str(out_dir),
            "--bank", str(tmp_path / "bank.json"), "--no-llm",
        ])
        data = json.loads((out_dir / "diagnosis.json").read_text(encoding="utf-8"))
        assert data["n_students"] == 12
        assert len(data["items"]) == 4
        q4 = next(i for i in data["items"] if i["item_id"] == "Q4")
        assert q4["severity"] == "CRITICAL"
        assert q4["point_biserial"] < 0

    def test_bad_csv_returns_error_code(self, tmp_path):
        bad = tmp_path / "bad.csv"
        bad.write_text("", encoding="utf-8")
        assert main(["analyze", str(bad), "--no-llm"]) == 1


class TestBankSearchCommand:
    def test_search_after_analyze(self, sample_csv, tmp_path, capsys):
        bank = tmp_path / "bank.json"
        main(["analyze", str(sample_csv), "--out", str(tmp_path / "o"),
              "--bank", str(bank), "--no-llm"])
        code = main(["bank-search", "--bank", str(bank), "--severity", "CRITICAL"])
        assert code == 0
        out = capsys.readouterr().out
        assert "Q4" in out
