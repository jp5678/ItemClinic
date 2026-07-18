"""학교 '문항 분석표'(요약 형식) 파싱·진단 테스트."""
import pytest

from itemclinic.diagnose import Severity
from itemclinic.profiles import get_profile
from itemclinic.summary import looks_like_summary, parse_summary


def school_rows():
    """스크린샷과 동일한 구조의 문항 분석표."""
    return [
        ["", "문항 분석표", "", "", "", "", "", "", "", "", "", "", "", ""],
        [],
        ["응시학과", "간호학과", "", "응시과목", "26-1 디지털리터러시와 AI활용(기말)",
         "", "", "시험일자", "2026-06-17", "", "", "응시인원", "", "229"],
        ["총배점", "40", "", "전체평균", "27.75", "", "", "표준편차", "4.59",
         "", "", "정답률", "", "69.4%"],
        [],
        ["문항 번호", "유형", "정답", "최다오답 선택지", "답지반응률(%)", "", "", "", "",
         "정답률 (%)", "문항 변별도", "난이도", "평균", "표준편차"],
        ["", "", "", "", "1", "2", "3", "4", "5", "", "", "", "", ""],
        ["1", "디지털 기초 개념 이해", "3", "2", "5.2", "12.7", "75.5", "4.4", "2.2",
         "75.5", "0.42", "중", "0.76", "0.43"],
        ["2", "AI 윤리", "1", "4", "45.0", "10.0", "8.0", "35.0", "2.0",
         "45.0", "-0.14", "어려움", "0.45", "0.50"],
        ["3", "정보 검색", "5", "2", "1.0", "2.0", "0.5", "1.5", "95.0",
         "95.0", "0.05", "쉬움", "0.95", "0.22"],
    ]


class TestDetection:
    def test_school_format_detected(self):
        assert looks_like_summary(school_rows())

    def test_response_matrix_not_detected(self):
        rows = [["student", "Q1", "Q2"], ["KEY", "A", "B"], ["S1", "A", "B"]]
        assert not looks_like_summary(rows)


class TestParsing:
    @pytest.fixture
    def exam(self):
        return parse_summary(school_rows(), get_profile("기말고사"))

    def test_metadata(self, exam):
        assert exam.meta.subject == "26-1 디지털리터러시와 AI활용(기말)"
        assert exam.meta.department == "간호학과"
        assert exam.meta.n_students == 229
        assert exam.meta.mean == pytest.approx(27.75)
        assert exam.meta.sd == pytest.approx(4.59)
        assert exam.meta.overall_p == pytest.approx(0.694)

    def test_items_parsed(self, exam):
        assert len(exam.items) == 3
        first = exam.items[0]
        assert first.item.number == "1"
        assert first.item.key == "3"
        assert first.item.item_type == "디지털 기초 개념 이해"
        assert first.stats.difficulty == pytest.approx(0.755)
        assert first.stats.point_biserial == pytest.approx(0.42)

    def test_option_rates_normalized(self, exam):
        rates = dict(exam.items[0].item.option_rates)
        assert rates["3"] == pytest.approx(0.755)
        assert sum(r for r in rates.values()) == pytest.approx(1.0, abs=0.01)

    def test_negative_discrimination_critical(self, exam):
        item2 = exam.items[1]
        assert item2.diagnosis.severity == Severity.CRITICAL

    def test_top_wrong_over_key_flagged(self, exam):
        # 2번 문항: 정답 1(45%)과 근접한 오답 4(35%) — 오답 우세는 아님.
        # 여기서는 '정답보다 선택률 높은 오답' 케이스를 별도 행으로 검증한다.
        rows = school_rows()
        rows.append(["4", "네트워크", "2", "3", "10.0", "20.0", "60.0", "5.0", "5.0",
                     "20.0", "0.10", "어려움", "0.20", "0.40"])
        exam2 = parse_summary(rows, get_profile("기말고사"))
        item4 = exam2.items[3]
        assert item4.diagnosis.severity == Severity.CRITICAL
        assert any("정답" in f.message and "오답" in f.message
                   for f in item4.diagnosis.flags)

    def test_dead_distractor_flagged(self, exam):
        item3 = exam.items[2]
        assert any("기능하지" in f.message for f in item3.diagnosis.flags)

    def test_headerless_rows_raise(self):
        with pytest.raises(ValueError):
            parse_summary([["아무", "내용"]], get_profile("일반"))

    def test_sub_one_percent_rate_not_misread(self):
        # 답지반응률 '0.5'는 0.5%이지 비율 50%가 아니다 (열 단위 스케일 판정)
        rows = school_rows()
        exam = parse_summary(rows, get_profile("기말고사"))
        rates3 = dict(exam.items[2].item.option_rates)
        assert rates3["3"] == pytest.approx(0.005)
        # 정상 변별도의 3번 문항이 '오답 우세'로 오판되면 안 됨
        assert not any(f.code == "WRONG_OVER_KEY"
                       for f in exam.items[2].diagnosis.flags)

    def test_proportion_scale_columns_kept(self):
        # 정답률 열이 이미 0~1 비율(엑셀 % 서식의 내부값)이어도 그대로 해석
        rows = [
            ["문항", "정답", "정답률", "변별도"],
            ["1", "2", "0.755", "0.42"],
            ["2", "1", "0.45", "0.30"],
        ]
        exam = parse_summary(rows, get_profile("일반"))
        assert exam.items[0].stats.difficulty == pytest.approx(0.755)
