"""stats 모듈 단위 테스트: 난이도, 변별도, KR-20."""
import pytest

from itemclinic.stats import (
    difficulty,
    point_biserial_rest,
    upper_lower_index,
    kr20,
    kr20_if_deleted,
)

# 5명 x 4문항 채점 행렬 (1=정답, 0=오답)
MATRIX = [
    [1, 1, 1, 0],
    [1, 1, 0, 0],
    [1, 0, 1, 1],
    [0, 1, 0, 0],
    [0, 0, 0, 1],
]


class TestDifficulty:
    def test_basic(self):
        p = difficulty(MATRIX)
        assert p == pytest.approx([0.6, 0.6, 0.4, 0.4])

    def test_all_correct(self):
        assert difficulty([[1], [1]]) == [1.0]

    def test_empty_matrix_raises(self):
        with pytest.raises(ValueError):
            difficulty([])


class TestPointBiserialRest:
    def test_positive_discrimination(self):
        # 총점 높은 학생이 맞히는 문항은 양의 변별도
        r = point_biserial_rest(MATRIX, 0)
        assert r > 0

    def test_negative_discrimination(self):
        # 총점 낮은 학생만 맞히는 문항은 음의 변별도
        matrix = [
            [0, 1, 1, 1],
            [0, 1, 1, 0],
            [1, 0, 0, 0],
            [1, 0, 0, 0],
        ]
        assert point_biserial_rest(matrix, 0) < 0

    def test_zero_variance_item_returns_zero(self):
        matrix = [[1, 1], [1, 0], [1, 1]]
        assert point_biserial_rest(matrix, 0) == 0.0


class TestUpperLowerIndex:
    def test_perfect_discrimination(self):
        # 상위그룹 전원 정답, 하위그룹 전원 오답 -> D = 1.0
        matrix = [[1, s // 2] for s in range(8)]  # 총점으로 상하위 갈림
        matrix = [
            [1, 1], [1, 1], [1, 1],  # 상위
            [0, 0], [0, 0], [0, 0],  # 하위
        ]
        d = upper_lower_index(matrix, 0, fraction=0.5)
        assert d == pytest.approx(1.0)

    def test_no_discrimination(self):
        matrix = [[1, 1], [1, 1], [1, 0], [1, 0]]
        assert upper_lower_index(matrix, 0, fraction=0.5) == pytest.approx(0.0)


class TestKR20:
    def test_range(self):
        assert -1.0 <= kr20(MATRIX) <= 1.0

    def test_known_value(self):
        # 손계산 검증: k=2, 완전 상관 문항 쌍
        matrix = [[1, 1], [1, 1], [0, 0], [0, 0]]
        assert kr20(matrix) == pytest.approx(1.0)

    def test_zero_total_variance(self):
        matrix = [[1, 0], [0, 1], [1, 0]]
        assert kr20(matrix) == 0.0

    def test_single_item_raises(self):
        with pytest.raises(ValueError):
            kr20([[1], [0]])


class TestKR20IfDeleted:
    def test_returns_one_value_per_item(self):
        values = kr20_if_deleted(MATRIX)
        assert len(values) == 4

    def test_deleting_bad_item_raises_alpha(self):
        # 문항 3(음의 변별)을 지우면 신뢰도가 올라가야 함
        matrix = [
            [1, 1, 1, 0],
            [1, 1, 1, 0],
            [1, 1, 0, 1],
            [0, 0, 0, 1],
            [0, 0, 0, 1],
        ]
        base = kr20(matrix)
        deleted = kr20_if_deleted(matrix)
        assert deleted[3] > base
