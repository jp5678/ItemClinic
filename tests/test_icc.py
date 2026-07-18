"""icc 모듈 테스트: 경험적 문항특성곡선."""
import pytest

from itemclinic.icc import empirical_icc


def make_matrix():
    # 총점 스펙트럼이 넓은 20명 x 2문항
    # 문항0: 능력 비례(정상), 문항1: 역방향(불량)
    rows = []
    for i in range(20):
        ability = i / 19
        rows.append([1 if ability > 0.5 else 0, 1 if ability < 0.3 else 0])
    return rows


class TestEmpiricalICC:
    def test_group_count(self):
        curve = empirical_icc(make_matrix(), 0, n_groups=5)
        assert len(curve) == 5

    def test_monotone_item_rises(self):
        curve = empirical_icc(make_matrix(), 0, n_groups=4)
        props = [g.proportion_correct for g in curve]
        assert props[0] <= props[-1]

    def test_bad_item_falls(self):
        curve = empirical_icc(make_matrix(), 1, n_groups=4)
        props = [g.proportion_correct for g in curve]
        assert props[0] > props[-1]

    def test_group_sizes_sum_to_n(self):
        curve = empirical_icc(make_matrix(), 0, n_groups=5)
        assert sum(g.n for g in curve) == 20

    def test_too_few_students_raises(self):
        with pytest.raises(ValueError):
            empirical_icc([[1, 0]], 0, n_groups=5)
