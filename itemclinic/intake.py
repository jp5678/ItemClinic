"""입력 파일 자동 인식: 학생별 응답 행렬 vs 학교 '문항 분석표'(요약).

요약 형식이면 상단 텍스트 영역을 메타데이터로 참조해야 하므로
skip_rows를 무시하고 전체 시트를 해석한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .loader import EXCEL_SUFFIXES, LoadError, _read_raw_rows, load_responses
from .models import ResponseData
from .profiles import RuleProfile
from .summary import SummaryExam, looks_like_summary, parse_summary


@dataclass(frozen=True)
class Intake:
    kind: str                                # "responses" | "summary"
    responses: Optional[ResponseData] = None
    summary: Optional[SummaryExam] = None


def load_any(path, skip_rows: int, profile: RuleProfile) -> Intake:
    """파일 형식을 감지해 알맞은 파서로 읽는다."""
    path = Path(path)
    is_excel = path.suffix.lower() in EXCEL_SUFFIXES
    rows = _read_raw_rows(path, is_excel)
    if looks_like_summary(rows):
        try:
            return Intake(kind="summary", summary=parse_summary(rows, profile))
        except ValueError as exc:
            raise LoadError(str(exc)) from exc
    return Intake(kind="responses",
                  responses=load_responses(path, skip_rows=skip_rows))
