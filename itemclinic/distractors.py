"""오답지(매력도) 분석.

선택지별 전체/상위/하위 집단 선택률을 계산한다.
- 상위 집단이 정답보다 많이 고르는 오답 → 정답 오류·중의성 의심
- 아무도 안 고르는 오답(<5%) → 기능하지 않는 오답지
"""
from __future__ import annotations

from typing import Sequence, Tuple

from .models import OptionStats


def analyze_distractors(
    raw: Sequence[Sequence[str]],
    scored: Sequence[Sequence[int]],
    key: Sequence[str],
    item_index: int,
    fraction: float = 0.27,
) -> Tuple[OptionStats, ...]:
    """한 문항의 선택지별 반응 분포를 반환한다 (선택률 내림차순)."""
    if not raw:
        raise ValueError("원 응답 데이터가 없습니다.")
    if not 0 < fraction <= 0.5:
        raise ValueError("fraction은 0과 0.5 사이여야 합니다.")

    responses = [row[item_index].strip().upper() for row in raw]
    correct = key[item_index].strip().upper()

    order = sorted(range(len(scored)), key=lambda i: sum(scored[i]), reverse=True)
    k = max(1, round(len(scored) * fraction))
    upper_set = set(order[:k])
    lower_set = set(order[-k:])

    options = sorted({r for r in responses if r != ""} | {correct})
    result = []
    for opt in options:
        chosen = [i for i, r in enumerate(responses) if r == opt]
        result.append(OptionStats(
            option=opt,
            is_key=(opt == correct),
            overall_rate=len(chosen) / len(responses),
            upper_rate=sum(1 for i in chosen if i in upper_set) / k,
            lower_rate=sum(1 for i in chosen if i in lower_set) / k,
        ))
    return tuple(sorted(result, key=lambda o: o.overall_rate, reverse=True))
