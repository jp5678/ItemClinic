"""시험 유형별 진단 규칙 프로파일.

- 규준참조(중간·기말·퀴즈): 학생 간 변별이 목적 → 통용 기준 그대로.
- 진단평가(준거참조): 선수학습 결손 확인이 목적 → 낮은 정답률은 결손의 증거이므로
  '너무 어려움' 플래그를 끈다.
- 형성평가(준거참조·완전학습): 대부분이 도달했는지 확인이 목적 → 높은 정답률이
  정상이므로 '너무 쉬움' 플래그를 끈다. 변별도 기준도 완화한다.
음의 변별도는 어떤 유형에서도 문항 결함 신호이므로 항상 불량 처리한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RuleProfile:
    name: str
    description: str
    criterion_referenced: bool      # 준거참조 여부 (KR-20 해석 문구에 사용)
    difficulty_hard: Optional[float]   # p가 이보다 낮으면 '너무 어려움' (None=검사 안 함)
    difficulty_easy: Optional[float]   # p가 이보다 높으면 '너무 쉬움' (None=검사 안 함)
    disc_poor: float                # 변별도 불량 기준
    disc_marginal: float            # 변별도 주의 기준
    check_alpha_gain: bool          # 삭제 시 KR-20 상승 플래그 사용 여부


_NORM = dict(
    criterion_referenced=False,
    difficulty_hard=0.20,
    difficulty_easy=0.90,
    disc_poor=0.10,
    disc_marginal=0.20,
    check_alpha_gain=True,
)

EXAM_TYPES = {
    "일반": RuleProfile(name="일반", description="규준참조 일반 시험", **_NORM),
    "중간고사": RuleProfile(name="중간고사", description="규준참조 총괄평가", **_NORM),
    "기말고사": RuleProfile(name="기말고사", description="규준참조 총괄평가", **_NORM),
    "퀴즈": RuleProfile(name="퀴즈", description="규준참조 소형 평가", **_NORM),
    "진단평가": RuleProfile(
        name="진단평가",
        description="준거참조 — 선수학습 결손 진단 (낮은 정답률 허용)",
        criterion_referenced=True,
        difficulty_hard=None,
        difficulty_easy=0.95,
        disc_poor=0.05,
        disc_marginal=0.15,
        check_alpha_gain=False,
    ),
    "형성평가": RuleProfile(
        name="형성평가",
        description="준거참조 — 완전학습 확인 (높은 정답률 허용)",
        criterion_referenced=True,
        difficulty_hard=0.20,
        difficulty_easy=None,
        disc_poor=0.05,
        disc_marginal=0.15,
        check_alpha_gain=False,
    ),
}

DEFAULT_PROFILE = EXAM_TYPES["일반"]


def get_profile(exam_type: str) -> RuleProfile:
    """시험 유형명으로 프로파일을 찾는다. 없으면 ValueError."""
    profile = EXAM_TYPES.get(exam_type)
    if profile is None:
        valid = ", ".join(EXAM_TYPES)
        raise ValueError(f"알 수 없는 시험 유형 '{exam_type}'. 사용 가능: {valid}")
    return profile
