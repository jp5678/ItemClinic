"""불량문항 진단 규칙.

기준은 시험 유형별 RuleProfile(profiles.py)이 정한다.
규준참조 기본값: 난이도 p 0.20~0.90, 변별도 0.10/0.20, 삭제 시 KR-20 상승 검사.
음의 변별도는 유형과 무관하게 항상 불량이다.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Tuple

from .models import ItemStats
from .profiles import DEFAULT_PROFILE, RuleProfile

DISC_NEGATIVE = 0.0
ALPHA_GAIN_EPS = 0.005


class Severity(enum.IntEnum):
    OK = 0
    WARNING = 1
    CRITICAL = 2


@dataclass(frozen=True)
class Flag:
    code: str
    severity: Severity
    message: str


@dataclass(frozen=True)
class Diagnosis:
    item_id: str
    severity: Severity
    flags: Tuple[Flag, ...]


def diagnose_item(
    stats: ItemStats,
    test_kr20: float,
    profile: RuleProfile = DEFAULT_PROFILE,
) -> Diagnosis:
    """문항 통계에 프로파일 규칙을 적용해 플래그 목록과 종합 심각도를 반환한다."""
    flags = (
        _check_discrimination(stats, profile)
        + _check_difficulty(stats, profile)
        + _check_reliability(stats, test_kr20, profile)
    )
    severity = max((f.severity for f in flags), default=Severity.OK)
    return Diagnosis(item_id=stats.item_id, severity=severity, flags=tuple(flags))


def _check_discrimination(s: ItemStats, p: RuleProfile) -> tuple:
    r = s.point_biserial
    if r < DISC_NEGATIVE:
        return (Flag(
            "DISC_NEGATIVE", Severity.CRITICAL,
            f"변별도가 음수입니다(r={r:.2f}). 총점이 높은 학생일수록 오히려 틀리는 문항으로, "
            "정답 오류·중의적 표현·상위권을 함정에 빠뜨리는 매력적 오답 가능성이 큽니다. "
            "폐기 또는 전면 수정을 권합니다.",
        ),)
    if r < p.disc_poor:
        return (Flag(
            "DISC_POOR", Severity.CRITICAL,
            f"변별도가 매우 낮습니다(r={r:.2f} < {p.disc_poor}). "
            "능력 수준과 무관하게 정답률이 결정되는 문항입니다.",
        ),)
    if r < p.disc_marginal:
        return (Flag(
            "DISC_MARGINAL", Severity.WARNING,
            f"변별도가 낮은 편입니다(r={r:.2f} < {p.disc_marginal}). 오답지 점검을 권합니다.",
        ),)
    return ()


def _check_difficulty(s: ItemStats, prof: RuleProfile) -> tuple:
    p = s.difficulty
    if prof.difficulty_hard is not None and p < prof.difficulty_hard:
        return (Flag(
            "TOO_HARD", Severity.WARNING,
            f"난이도 p={p:.2f}로 너무 어렵습니다(기준 {prof.difficulty_hard} 미만). "
            "추측 응답이 섞여 변별력이 떨어질 수 있습니다.",
        ),)
    if prof.difficulty_easy is not None and p > prof.difficulty_easy:
        return (Flag(
            "TOO_EASY", Severity.WARNING,
            f"난이도 p={p:.2f}로 너무 쉽습니다(기준 {prof.difficulty_easy} 초과). "
            "변별에 기여하지 못하는 문항입니다.",
        ),)
    return ()


def _check_reliability(s: ItemStats, test_kr20: float, p: RuleProfile) -> tuple:
    if not p.check_alpha_gain:
        return ()
    gain = s.kr20_if_deleted - test_kr20
    if gain > ALPHA_GAIN_EPS:
        return (Flag(
            "ALPHA_GAIN", Severity.WARNING,
            f"이 문항을 삭제하면 KR-20이 {test_kr20:.3f} → {s.kr20_if_deleted:.3f}으로 "
            "상승합니다. 검사 전체 신뢰도를 낮추는 문항입니다.",
        ),)
    return ()
