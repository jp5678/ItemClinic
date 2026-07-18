"""경험적 문항특성곡선(empirical ICC).

총점 기준으로 학생을 능력 그룹(기본 5개)으로 나누고,
그룹별 해당 문항 정답률을 곡선의 점으로 반환한다.
정상 문항은 우상향, 불량 문항은 평평하거나 우하향한다.
"""
from __future__ import annotations

from typing import Sequence, Tuple

from .models import ICCGroup

Matrix = Sequence[Sequence[int]]


def empirical_icc(matrix: Matrix, item_index: int, n_groups: int = 5) -> Tuple[ICCGroup, ...]:
    """총점 오름차순 그룹별 정답률 곡선을 반환한다."""
    if n_groups < 2:
        raise ValueError("그룹 수는 2 이상이어야 합니다.")
    if len(matrix) < n_groups:
        raise ValueError(
            f"학생 수({len(matrix)})가 그룹 수({n_groups})보다 적어 ICC를 그릴 수 없습니다."
        )
    order = sorted(range(len(matrix)), key=lambda i: sum(matrix[i]))
    groups = _split_even(order, n_groups)

    curve = []
    for g_idx, members in enumerate(groups):
        totals = [sum(matrix[i]) for i in members]
        correct = [matrix[i][item_index] for i in members]
        curve.append(ICCGroup(
            group_index=g_idx,
            n=len(members),
            mean_total=sum(totals) / len(totals),
            proportion_correct=sum(correct) / len(correct),
        ))
    return tuple(curve)


def _split_even(order: Sequence[int], n_groups: int):
    """정렬된 인덱스를 크기가 최대한 균등한 연속 그룹으로 나눈다."""
    n = len(order)
    base, extra = divmod(n, n_groups)
    groups, start = [], 0
    for g in range(n_groups):
        size = base + (1 if g < extra else 0)
        groups.append(list(order[start:start + size]))
        start += size
    return groups
