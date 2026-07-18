"""loader 모듈 테스트: CSV 파싱/검증/채점."""
import textwrap

import pytest

from itemclinic.loader import load_responses, LoadError


def write_csv(tmp_path, content):
    path = tmp_path / "resp.csv"
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


class TestRawResponses:
    def test_key_row_scoring(self, tmp_path):
        path = write_csv(tmp_path, """\
            student,Q1,Q2,Q3
            KEY,A,B,C
            s1,A,B,C
            s2,A,C,C
            s3,B,B,D
        """)
        data = load_responses(path)
        assert data.item_ids == ("Q1", "Q2", "Q3")
        assert data.scored == ((1, 1, 1), (1, 0, 1), (0, 1, 0))
        assert data.key == ("A", "B", "C")
        assert data.raw is not None

    def test_prescored_binary(self, tmp_path):
        path = write_csv(tmp_path, """\
            student,Q1,Q2
            s1,1,0
            s2,0,1
        """)
        data = load_responses(path)
        assert data.scored == ((1, 0), (0, 1))
        assert data.key is None
        assert data.raw is None

    def test_missing_response_scored_zero(self, tmp_path):
        path = write_csv(tmp_path, """\
            student,Q1,Q2
            KEY,A,B
            s1,,B
        """)
        data = load_responses(path)
        assert data.scored == ((0, 1),)


class TestValidation:
    def test_empty_file(self, tmp_path):
        path = write_csv(tmp_path, "")
        with pytest.raises(LoadError):
            load_responses(path)

    def test_no_students(self, tmp_path):
        path = write_csv(tmp_path, "student,Q1\nKEY,A\n")
        with pytest.raises(LoadError):
            load_responses(path)

    def test_ragged_row(self, tmp_path):
        path = write_csv(tmp_path, "student,Q1,Q2\nKEY,A,B\ns1,A\n")
        with pytest.raises(LoadError):
            load_responses(path)

    def test_non_binary_without_key(self, tmp_path):
        path = write_csv(tmp_path, "student,Q1\ns1,A\n")
        with pytest.raises(LoadError):
            load_responses(path)
