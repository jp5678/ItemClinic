"""시험 유형별 진단 프로파일 테스트."""
import pytest

from itemclinic.diagnose import diagnose_item, Severity
from itemclinic.models import ItemStats
from itemclinic.profiles import EXAM_TYPES, get_profile


def make_stats(**overrides):
    base = dict(
        item_id="Q1",
        difficulty=0.55,
        point_biserial=0.35,
        upper_lower=0.30,
        kr20_if_deleted=0.60,
    )
    base.update(overrides)
    return ItemStats(**base)


class TestProfiles:
    def test_known_exam_types_exist(self):
        for name in ("일반", "진단평가", "형성평가", "중간고사", "기말고사", "퀴즈"):
            assert name in EXAM_TYPES

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError):
            get_profile("없는유형")

    def test_formative_allows_easy_items(self):
        # 형성평가(완전학습 확인)는 정답률 95%가 정상
        stats = make_stats(difficulty=0.96)
        norm = diagnose_item(stats, test_kr20=0.65, profile=get_profile("중간고사"))
        formative = diagnose_item(stats, test_kr20=0.65, profile=get_profile("형성평가"))
        assert norm.severity != Severity.OK
        assert formative.severity == Severity.OK

    def test_diagnostic_allows_hard_items(self):
        # 진단평가(사전 결손 확인)는 정답률 10%가 정보로서 정상
        stats = make_stats(difficulty=0.10)
        norm = diagnose_item(stats, test_kr20=0.65, profile=get_profile("기말고사"))
        diag = diagnose_item(stats, test_kr20=0.65, profile=get_profile("진단평가"))
        assert norm.severity != Severity.OK
        assert diag.severity == Severity.OK

    def test_negative_discrimination_critical_everywhere(self):
        # 음의 변별도는 어떤 시험 유형에서도 불량
        stats = make_stats(point_biserial=-0.14)
        for name in EXAM_TYPES:
            result = diagnose_item(stats, test_kr20=0.65, profile=get_profile(name))
            assert result.severity == Severity.CRITICAL, name

    def test_default_profile_is_norm_referenced(self):
        stats = make_stats(difficulty=0.96)
        result = diagnose_item(stats, test_kr20=0.65)
        assert result.severity != Severity.OK
