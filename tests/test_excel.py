"""엑셀(.xlsx) 로딩 + 상단 제외 행(skip_rows) 테스트."""
import pytest

openpyxl = pytest.importorskip("openpyxl")

from itemclinic.loader import load_responses, LoadError

TITLE_ROWS = [
    ["2026학년도 1학기 성인간호학"], [], ["중간고사 응답 결과"],
    ["출력일: 2026-07-18"], [], ["담당: 간호학과"], ["-"],
]


def write_xlsx(path, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    wb.save(path)


def data_rows():
    return [
        ["student", "Q1", "Q2", "Q3"],
        ["KEY", "A", "B", "C"],
        ["S001", "A", "B", "C"],
        ["S002", "A", "C", "C"],
        ["S003", "B", "B", "D"],
    ]


class TestExcelLoading:
    def test_basic_xlsx(self, tmp_path):
        path = tmp_path / "exam.xlsx"
        write_xlsx(path, data_rows())
        data = load_responses(path)
        assert data.item_ids == ("Q1", "Q2", "Q3")
        assert data.scored == ((1, 1, 1), (1, 0, 1), (0, 1, 0))

    def test_skip_seven_title_rows(self, tmp_path):
        # 학교 시스템 출력 형식: 1~7행이 제목 영역
        path = tmp_path / "exam.xlsx"
        write_xlsx(path, TITLE_ROWS + data_rows())
        data = load_responses(path, skip_rows=7)
        assert data.item_ids == ("Q1", "Q2", "Q3")
        assert data.n_students == 3

    def test_numeric_cells_become_int_strings(self, tmp_path):
        # 응답이 1~5 숫자인 경우 (엑셀은 숫자를 float로 저장)
        path = tmp_path / "exam.xlsx"
        write_xlsx(path, [
            ["student", "Q1", "Q2"],
            ["KEY", 1, 3],
            ["S001", 1, 3],
            ["S002", 2, 3],
        ])
        data = load_responses(path)
        assert data.scored == ((1, 1), (0, 1))

    def test_ragged_excel_rows_padded(self, tmp_path):
        # 엑셀은 뒤쪽 빈 셀을 아예 저장하지 않는 경우가 흔함
        path = tmp_path / "exam.xlsx"
        write_xlsx(path, [
            ["student", "Q1", "Q2"],
            ["KEY", "A", "B"],
            ["S001", "A"],  # Q2 무응답
        ])
        data = load_responses(path)
        assert data.scored == ((1, 0),)

    def test_old_xls_rejected_with_guidance(self, tmp_path):
        path = tmp_path / "exam.xls"
        path.write_bytes(b"\xd0\xcf\x11\xe0old-binary")
        with pytest.raises(LoadError, match="xlsx"):
            load_responses(path)


class TestSkipRowsCsv:
    def test_skip_rows_on_csv(self, tmp_path):
        path = tmp_path / "exam.csv"
        lines = ["제목,,", ",,", "출력일,,", ",,", ",,", ",,", "비고,,",
                 "student,Q1,Q2", "KEY,A,B", "S001,A,B"]
        path.write_text("\n".join(lines), encoding="utf-8")
        data = load_responses(path, skip_rows=7)
        assert data.item_ids == ("Q1", "Q2")
        assert data.scored == ((1, 1),)

    def test_skip_too_many_rows(self, tmp_path):
        path = tmp_path / "exam.csv"
        path.write_text("student,Q1\nKEY,A\ns1,A\n", encoding="utf-8")
        with pytest.raises(LoadError):
            load_responses(path, skip_rows=10)
