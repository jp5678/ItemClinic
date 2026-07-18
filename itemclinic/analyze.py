"""분석 오케스트레이터: 응답 데이터 -> 검사/문항 통계 + 진단."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from . import stats as st
from .diagnose import Diagnosis, diagnose_item
from .distractors import analyze_distractors
from .icc import empirical_icc
from .models import ICCGroup, ItemStats, OptionStats, ResponseData
from .profiles import DEFAULT_PROFILE, RuleProfile

ICC_GROUPS = 5


@dataclass(frozen=True)
class ItemResult:
    stats: ItemStats
    diagnosis: Diagnosis
    icc: Tuple[ICCGroup, ...]
    distractors: Optional[Tuple[OptionStats, ...]]


@dataclass(frozen=True)
class ExamResult:
    n_students: int
    n_items: int
    kr20: float
    mean_score: float
    sd_score: float
    items: Tuple[ItemResult, ...]
    profile: RuleProfile = DEFAULT_PROFILE


def analyze_exam(data: ResponseData, profile: RuleProfile = DEFAULT_PROFILE) -> ExamResult:
    """전체 파이프라인: 통계 산출 -> ICC -> 오답지 분석 -> 진단."""
    matrix = data.scored
    test_kr20 = st.kr20(matrix)
    p_values = st.difficulty(matrix)
    deleted = st.kr20_if_deleted(matrix)

    items = []
    for j, item_id in enumerate(data.item_ids):
        item_stats = ItemStats(
            item_id=item_id,
            difficulty=p_values[j],
            point_biserial=st.point_biserial_rest(matrix, j),
            upper_lower=st.upper_lower_index(matrix, j),
            kr20_if_deleted=deleted[j],
        )
        dist = None
        if data.raw is not None and data.key is not None:
            dist = analyze_distractors(data.raw, matrix, data.key, j)
        items.append(ItemResult(
            stats=item_stats,
            diagnosis=diagnose_item(item_stats, test_kr20, profile),
            icc=empirical_icc(matrix, j, n_groups=min(ICC_GROUPS, len(matrix))),
            distractors=dist,
        ))

    totals = [sum(row) for row in matrix]
    n = len(totals)
    mean = sum(totals) / n
    sd = (sum((t - mean) ** 2 for t in totals) / (n - 1)) ** 0.5 if n > 1 else 0.0
    return ExamResult(
        n_students=n,
        n_items=len(data.item_ids),
        kr20=test_kr20,
        mean_score=mean,
        sd_score=sd,
        items=tuple(items),
        profile=profile,
    )
