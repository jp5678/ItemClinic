"""diagnose 모듈 테스트: 불량문항 판정 규칙."""
from itemclinic.diagnose import diagnose_item, Severity
from itemclinic.models import ItemStats


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


class TestDiagnoseItem:
    def test_healthy_item_no_flags(self):
        result = diagnose_item(make_stats(), test_kr20=0.65)
        assert result.flags == ()
        assert result.severity == Severity.OK

    def test_negative_discrimination_is_critical(self):
        stats = make_stats(point_biserial=-0.14, upper_lower=-0.10)
        result = diagnose_item(stats, test_kr20=0.65)
        assert result.severity == Severity.CRITICAL
        assert any("변별도" in f.message for f in result.flags)

    def test_too_easy_flagged(self):
        result = diagnose_item(make_stats(difficulty=0.96), test_kr20=0.65)
        assert result.severity != Severity.OK

    def test_too_hard_flagged(self):
        result = diagnose_item(make_stats(difficulty=0.12), test_kr20=0.65)
        assert result.severity != Severity.OK

    def test_low_discrimination_warning(self):
        stats = make_stats(point_biserial=0.12, upper_lower=0.10)
        result = diagnose_item(stats, test_kr20=0.65)
        assert result.severity == Severity.WARNING

    def test_reliability_gain_on_deletion_flagged(self):
        stats = make_stats(kr20_if_deleted=0.70)
        result = diagnose_item(stats, test_kr20=0.65)
        assert any("신뢰도" in f.message for f in result.flags)
