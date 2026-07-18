"""공용 불변 데이터 모델."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class ResponseData:
    """채점된 응답 데이터.

    scored: 학생 x 문항 0/1 행렬
    raw: 원 응답(선택지 문자) 행렬 — 0/1로 이미 채점된 입력이면 None
    key: 정답 키 — raw가 없으면 None
    """

    item_ids: Tuple[str, ...]
    student_ids: Tuple[str, ...]
    scored: Tuple[Tuple[int, ...], ...]
    raw: Optional[Tuple[Tuple[str, ...], ...]]
    key: Optional[Tuple[str, ...]]

    @property
    def n_students(self) -> int:
        return len(self.scored)

    @property
    def n_items(self) -> int:
        return len(self.item_ids)


@dataclass(frozen=True)
class ItemStats:
    """문항 하나의 고전검사이론 통계."""

    item_id: str
    difficulty: float          # 정답률 p
    point_biserial: float      # 수정 양류상관 (문항 제외 총점 기준)
    upper_lower: float         # 상하위 27% 변별도 D
    kr20_if_deleted: float     # 이 문항 삭제 시 KR-20


@dataclass(frozen=True)
class ICCGroup:
    """능력(총점) 그룹 하나의 정답률 점."""

    group_index: int
    n: int
    mean_total: float
    proportion_correct: float


@dataclass(frozen=True)
class OptionStats:
    """한 문항의 선택지 하나에 대한 반응 분포."""

    option: str
    is_key: bool
    overall_rate: float
    upper_rate: float
    lower_rate: float
