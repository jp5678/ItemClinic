"""고전검사이론(CTT) 통계: 난이도, 변별도, KR-20."""
from __future__ import annotations

import math
from typing import Sequence

Matrix = Sequence[Sequence[int]]


def _validate(matrix: Matrix) -> None:
    if not matrix or not matrix[0]:
        raise ValueError("응답 행렬이 비어 있습니다.")
    width = len(matrix[0])
    for i, row in enumerate(matrix):
        if len(row) != width:
            raise ValueError(f"{i + 1}번째 행의 문항 수가 다릅니다.")


def _total_scores(matrix: Matrix) -> list:
    return [sum(row) for row in matrix]


def _population_variance(values: Sequence[float]) -> float:
    # KR-20에서 문항 분산 pq가 모분산이므로 총점 분산도 모분산으로 통일한다.
    n = len(values)
    if n == 0:
        return 0.0
    mean = sum(values) / n
    return sum((v - mean) ** 2 for v in values) / n


def difficulty(matrix: Matrix) -> list:
    """문항별 난이도(정답률 p). 높을수록 쉬운 문항."""
    _validate(matrix)
    n = len(matrix)
    return [sum(row[j] for row in matrix) / n for j in range(len(matrix[0]))]


def point_biserial_rest(matrix: Matrix, item_index: int) -> float:
    """수정 양류상관: 문항 점수와 (해당 문항 제외) 총점의 상관.

    문항 제외 총점을 쓰면 자기 자신과의 상관으로 인한 과대추정을 막는다.
    분산이 0이면 0.0을 반환한다.
    """
    _validate(matrix)
    item = [row[item_index] for row in matrix]
    rest = [sum(row) - row[item_index] for row in matrix]
    return _pearson(item, rest)


def _pearson(x: Sequence[float], y: Sequence[float]) -> float:
    n = len(x)
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    cov = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
    var_x = sum((a - mean_x) ** 2 for a in x)
    var_y = sum((b - mean_y) ** 2 for b in y)
    if var_x == 0 or var_y == 0:
        return 0.0
    return cov / math.sqrt(var_x * var_y)


def upper_lower_index(matrix: Matrix, item_index: int, fraction: float = 0.27) -> float:
    """상하위 집단 변별도 D = P(상위) - P(하위).

    총점 기준 상위/하위 fraction(기본 27%) 집단의 정답률 차.
    """
    _validate(matrix)
    if not 0 < fraction <= 0.5:
        raise ValueError("fraction은 0과 0.5 사이여야 합니다.")
    order = sorted(range(len(matrix)), key=lambda i: sum(matrix[i]), reverse=True)
    k = max(1, round(len(matrix) * fraction))
    upper = [matrix[i][item_index] for i in order[:k]]
    lower = [matrix[i][item_index] for i in order[-k:]]
    return sum(upper) / len(upper) - sum(lower) / len(lower)


def kr20(matrix: Matrix) -> float:
    """KR-20 신뢰도 계수 (이분 문항용 Cronbach's alpha와 동치)."""
    _validate(matrix)
    k = len(matrix[0])
    if k < 2:
        raise ValueError("KR-20 계산에는 문항이 2개 이상 필요합니다.")
    total_var = _population_variance(_total_scores(matrix))
    if total_var == 0:
        return 0.0
    n = len(matrix)
    pq_sum = 0.0
    for j in range(k):
        p = sum(row[j] for row in matrix) / n
        pq_sum += p * (1 - p)
    return (k / (k - 1)) * (1 - pq_sum / total_var)


def kr20_if_deleted(matrix: Matrix) -> list:
    """각 문항을 삭제했을 때의 KR-20 목록."""
    _validate(matrix)
    k = len(matrix[0])
    if k < 3:
        raise ValueError("문항 삭제 시 신뢰도 계산에는 문항이 3개 이상 필요합니다.")
    results = []
    for j in range(k):
        reduced = [[v for idx, v in enumerate(row) if idx != j] for row in matrix]
        results.append(kr20(reduced))
    return results
