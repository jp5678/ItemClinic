"""distractors 모듈 테스트: 오답지 매력도 분석."""
import pytest

from itemclinic.distractors import analyze_distractors

RAW = (
    ("A", "B"),  # 상위 (총점으로 정렬됨을 가정하지 않음 — scored로 판단)
    ("A", "B"),
    ("A", "C"),
    ("B", "C"),
    ("C", "C"),
    ("B", "C"),
)
SCORED = (
    (1, 1),
    (1, 1),
    (1, 0),
    (0, 0),
    (0, 0),
    (0, 0),
)
KEY = ("A", "B")


class TestAnalyzeDistractors:
    def test_option_rates_sum_to_one(self):
        result = analyze_distractors(RAW, SCORED, KEY, 0)
        total = sum(o.overall_rate for o in result)
        assert total == pytest.approx(1.0)

    def test_correct_option_flagged(self):
        result = analyze_distractors(RAW, SCORED, KEY, 0)
        by_option = {o.option: o for o in result}
        assert by_option["A"].is_key
        assert not by_option["B"].is_key

    def test_upper_lower_rates(self):
        result = analyze_distractors(RAW, SCORED, KEY, 0, fraction=0.5)
        by_option = {o.option: o for o in result}
        # 상위 3명(총점 2,2,1)은 전원 A 선택
        assert by_option["A"].upper_rate == pytest.approx(1.0)
        assert by_option["A"].lower_rate == pytest.approx(0.0)
