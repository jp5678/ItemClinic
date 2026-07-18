"""학교 시스템 '문항 분석표'(요약 형식) 파싱과 진단.

학생별 원 응답이 아니라 문항별 집계(정답, 최다오답, 답지반응률, 정답률,
변별도, 난이도)가 담긴 엑셀/CSV를 해석한다. 상단 텍스트 영역의
응시학과·응시과목·시험일자·응시인원·전체평균·표준편차·정답률을 메타데이터로 읽는다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .diagnose import Diagnosis, Flag, Severity, diagnose_item
from .models import ItemStats
from .profiles import RuleProfile

Rows = Sequence[Sequence[str]]

META_LABELS = {
    "응시학과": "department",
    "응시과목": "subject",
    "시험일자": "exam_date",
    "응시인원": "n_students",
    "총배점": "total_points",
    "전체평균": "mean",
    "표준편차": "sd",
    "정답률": "overall_p",
}
DEAD_DISTRACTOR_RATE = 0.05


@dataclass(frozen=True)
class SummaryMeta:
    department: Optional[str] = None
    subject: Optional[str] = None
    exam_date: Optional[str] = None
    n_students: Optional[int] = None
    total_points: Optional[float] = None
    mean: Optional[float] = None
    sd: Optional[float] = None
    overall_p: Optional[float] = None


@dataclass(frozen=True)
class SummaryItem:
    number: str
    item_type: Optional[str]
    key: Optional[str]
    top_wrong: Optional[str]
    option_rates: Tuple[Tuple[str, float], ...]
    difficulty_label: Optional[str]


@dataclass(frozen=True)
class SummaryItemResult:
    item: SummaryItem
    stats: ItemStats
    diagnosis: Diagnosis


@dataclass(frozen=True)
class SummaryExam:
    meta: SummaryMeta
    profile: RuleProfile
    items: Tuple[SummaryItemResult, ...]


def looks_like_summary(rows: Rows) -> bool:
    """'문항 분석표' 요약 형식인지 감지한다."""
    text = " ".join(c for row in rows[:15] for c in row if c)
    return "변별도" in text and ("답지반응" in text or "문항 분석표" in text)


def parse_summary(rows: Rows, profile: RuleProfile) -> SummaryExam:
    """요약 분석표 전체를 파싱해 문항별 진단까지 수행한다."""
    header_idx, cols = _find_header(rows)
    meta = _parse_meta(rows[:header_idx])
    data_start = _find_data_start(rows, header_idx, cols)

    raw_items = [p for p in (_parse_item_row(row, cols) for row in rows[data_start:])
                 if p is not None]
    items = [_diagnose(p, profile) for p in _normalize_scales(raw_items)]
    if not items:
        raise ValueError(
            "문항 분석표에서 문항 데이터 행을 찾지 못했습니다. "
            "문항 번호 열이 숫자인지 확인해 주세요."
        )
    return SummaryExam(meta=meta, profile=profile, items=tuple(items))


@dataclass(frozen=True)
class _Columns:
    number: int
    item_type: Optional[int]
    key: Optional[int]
    top_wrong: Optional[int]
    rate_start: Optional[int]
    n_options: int
    p: int
    r: int
    difficulty_label: Optional[int]


def _find_header(rows: Rows):
    for idx, row in enumerate(rows):
        cells = [c.strip() for c in row]
        if not any("변별도" in c for c in cells):
            continue
        try:
            p_col = next(i for i, c in enumerate(cells) if "정답률" in c)
            r_col = next(i for i, c in enumerate(cells) if "변별도" in c)
            number_col = next(i for i, c in enumerate(cells) if "문항" in c and "변별" not in c)
        except StopIteration:
            continue
        cols = _Columns(
            number=number_col,
            item_type=_find_col(cells, "유형"),
            key=_find_exact(cells, "정답"),
            top_wrong=_find_col(cells, "최다오답"),
            rate_start=_find_col(cells, "답지반응"),
            n_options=5,
            p=p_col,
            r=r_col,
            difficulty_label=_find_exact(cells, "난이도"),
        )
        return idx, cols
    raise ValueError(
        "문항 분석표 헤더(문항/정답률/변별도)를 찾지 못했습니다. 형식을 확인해 주세요."
    )


def _find_col(cells: List[str], keyword: str) -> Optional[int]:
    for i, c in enumerate(cells):
        if keyword in c:
            return i
    return None


def _find_exact(cells: List[str], label: str) -> Optional[int]:
    for i, c in enumerate(cells):
        if c.replace(" ", "") == label:
            return i
    return None


def _find_data_start(rows: Rows, header_idx: int, cols: _Columns) -> int:
    """헤더 다음의 보조 헤더 행(답지 번호 1~5)을 건너뛴다."""
    idx = header_idx + 1
    if idx < len(rows):
        row = rows[idx]
        first = row[cols.number].strip() if cols.number < len(row) else ""
        rest = [c.strip() for c in row if c.strip()]
        if first == "" and rest and all(re.fullmatch(r"\d", c) for c in rest):
            return idx + 1
    return idx


def _parse_meta(rows: Rows) -> SummaryMeta:
    values = {}
    for row in rows:
        cells = [c.strip() for c in row]
        for i, cell in enumerate(cells):
            field = META_LABELS.get(cell.replace(" ", ""))
            if field is None or field in values:
                continue
            value = next((c for c in cells[i + 1:] if c), None)
            if value is not None:
                values[field] = value
    return SummaryMeta(
        department=values.get("department"),
        subject=values.get("subject"),
        exam_date=values.get("exam_date"),
        n_students=_to_int(values.get("n_students")),
        total_points=_to_float(values.get("total_points")),
        mean=_to_float(values.get("mean")),
        sd=_to_float(values.get("sd")),
        overall_p=_to_proportion(values.get("overall_p")),
    )


def _parse_item_row(row: Sequence[str], cols: _Columns) -> Optional[dict]:
    cells = [c.strip() for c in row]
    number = cells[cols.number] if cols.number < len(cells) else ""
    if not re.fullmatch(r"\d+", number):
        return None
    p = _to_float(_cell(cells, cols.p))
    r = _to_float(_cell(cells, cols.r))
    if p is None or r is None:
        return None
    rates: List[Tuple[str, float]] = []
    if cols.rate_start is not None:
        for k in range(cols.n_options):
            rate = _to_float(_cell(cells, cols.rate_start + k))
            if rate is not None:
                rates.append((str(k + 1), rate))
    return {
        "item": SummaryItem(
            number=number,
            item_type=_cell(cells, cols.item_type) or None,
            key=_cell(cells, cols.key) or None,
            top_wrong=_cell(cells, cols.top_wrong) or None,
            option_rates=tuple(rates),  # 원시값 — _normalize_scales에서 비율로 변환
            difficulty_label=_cell(cells, cols.difficulty_label) or None,
        ),
        "rates": tuple(rates),
        "p": p,
        "r": r,
    }


def _normalize_scales(raw_items: List[dict]) -> List[dict]:
    """정답률·답지반응률 단위를 열 단위로 판정해 0~1 비율로 통일한다.

    '0.5' 한 칸만 보면 0.5%인지 비율 50%인지 알 수 없으므로, 열 전체에
    1을 넘는 값이 하나라도 있으면 % 단위(÷100), 전부 1 이하면 비율로 본다.
    """
    p_scale = _column_scale(v["p"] for v in raw_items)
    rate_scale = _column_scale(r for v in raw_items for _, r in v["rates"])
    normalized = []
    for v in raw_items:
        rates = tuple((opt, r / rate_scale) for opt, r in v["rates"])
        item: SummaryItem = v["item"]
        normalized.append({
            "item": SummaryItem(
                number=item.number,
                item_type=item.item_type,
                key=item.key,
                top_wrong=item.top_wrong,
                option_rates=rates,
                difficulty_label=item.difficulty_label,
            ),
            "p": v["p"] / p_scale,
            "r": v["r"],
        })
    return normalized


def _column_scale(values) -> float:
    values = list(values)
    if values and max(values) > 1:
        return 100.0
    return 1.0


def _diagnose(parsed: dict, profile: RuleProfile) -> SummaryItemResult:
    item: SummaryItem = parsed["item"]
    stats = ItemStats(
        item_id=item.number,
        difficulty=parsed["p"],
        point_biserial=parsed["r"],
        upper_lower=0.0,        # 요약 자료에는 없음 (리포트에 표시하지 않음)
        kr20_if_deleted=0.0,    # KR-20 산출 불가 → 삭제 시 신뢰도 검사 미적용
    )
    base = diagnose_item(stats, test_kr20=0.0, profile=profile)
    extra = _distractor_flags(item, parsed["p"])
    flags = base.flags + extra
    severity = max((f.severity for f in flags), default=Severity.OK)
    return SummaryItemResult(
        item=item,
        stats=stats,
        diagnosis=Diagnosis(item_id=item.number, severity=severity, flags=flags),
    )


def _distractor_flags(item: SummaryItem, p: float) -> tuple:
    if not item.option_rates or item.key is None:
        return ()
    rates = dict(item.option_rates)
    key = item.key.strip()
    flags = []
    for opt, rate in rates.items():
        if opt != key and rate > rates.get(key, p):
            flags.append(Flag(
                "WRONG_OVER_KEY", Severity.CRITICAL,
                f"오답 {opt}번의 선택률({rate:.0%})이 정답 {key}번({rates.get(key, p):.0%})보다 "
                "높습니다. 정답 오류 또는 강한 중의성이 의심되므로 정답 확인이 필요합니다.",
            ))
    dead = [opt for opt, rate in rates.items()
            if opt != key and rate < DEAD_DISTRACTOR_RATE]
    if dead:
        # 판정 등급에는 영향 없는 참고 정보 (쉬운 문항에선 불가피한 현상)
        flags.append(Flag(
            "DEAD_DISTRACTOR", Severity.OK,
            f"참고: 선택률 5% 미만으로 기능하지 않는 오답지가 있습니다: {', '.join(dead)}번. "
            "문항 개정 시 매력도 있는 오답으로 교체를 권합니다.",
        ))
    return tuple(flags)


def _cell(cells: Sequence[str], idx: Optional[int]) -> str:
    if idx is None or idx >= len(cells):
        return ""
    return cells[idx].strip()


def _to_float(value: Optional[str]) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace("%", "").replace(",", "").strip())
    except ValueError:
        return None


def _to_int(value: Optional[str]) -> Optional[int]:
    f = _to_float(value)
    return int(f) if f is not None else None


def _to_proportion(value: Optional[str]) -> Optional[float]:
    """69.4, '69.4%', 0.694 를 모두 0~1 비율로 정규화한다."""
    f = _to_float(value)
    if f is None:
        return None
    return f / 100 if f > 1 else f
