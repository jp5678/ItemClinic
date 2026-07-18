"""응답 파일(CSV/엑셀) 로딩/검증/채점.

지원 형식 (첫 열 = 학생 ID, 이후 열 = 문항):
1) 원 응답 + 정답 키: 첫 데이터 행의 ID가 KEY(대소문자 무관)이고 각 셀은 선택지(A~E, 1~5 등)
2) 기채점 0/1 행렬: KEY 행 없이 모든 셀이 0 또는 1

파일 형식: .csv 또는 .xlsx (첫 번째 시트).
skip_rows: 학교 시스템 출력물처럼 상단에 제목 영역이 있으면 그 행 수만큼 제외한다.
빈 셀(무응답)은 오답(0) 처리한다.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import List

from .excel import ExcelError, read_excel_rows
from .models import ResponseData

KEY_LABELS = {"key", "정답", "answer"}
EXCEL_SUFFIXES = {".xlsx", ".xlsm"}


class LoadError(ValueError):
    """입력 파일 형식 오류. 사용자에게 그대로 보여줄 수 있는 한국어 메시지를 담는다."""


def load_responses(path, skip_rows: int = 0) -> ResponseData:
    """CSV/엑셀 파일을 읽어 채점된 ResponseData를 반환한다."""
    path = Path(path)
    if skip_rows < 0:
        raise LoadError("상단 제외 행 수는 0 이상이어야 합니다.")
    is_excel = path.suffix.lower() in EXCEL_SUFFIXES
    rows = _read_raw_rows(path, is_excel)

    if skip_rows:
        rows = rows[skip_rows:]
    rows = [r for r in rows if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise LoadError(
            "헤더와 데이터 행을 찾을 수 없습니다. "
            f"상단 제외 행 수({skip_rows})가 데이터 위치와 맞는지 확인하세요."
        )

    header = _trim_trailing_empty(rows[0])
    if len(header) < 2:
        raise LoadError("헤더에 문항 열이 없습니다. 첫 열은 학생 ID, 이후 열은 문항이어야 합니다.")
    item_ids = tuple(h.strip() for h in header[1:])
    body = _normalize_widths(rows[1:], len(header), lenient=is_excel)

    key, data_rows = _split_key(body)
    if not data_rows:
        raise LoadError("학생 응답 행이 없습니다.")

    student_ids = tuple(r[0].strip() for r in data_rows)
    cells = [[c.strip() for c in r[1:]] for r in data_rows]

    if key is not None:
        raw = tuple(tuple(row) for row in cells)
        scored = tuple(
            tuple(1 if _norm(c) == _norm(k) and c != "" else 0 for c, k in zip(row, key))
            for row in cells
        )
        return ResponseData(item_ids, student_ids, scored, raw, tuple(key))

    scored = tuple(tuple(_parse_binary(c, i, j) for j, c in enumerate(row))
                   for i, row in enumerate(cells))
    return ResponseData(item_ids, student_ids, scored, None, None)


def _read_raw_rows(path: Path, is_excel: bool) -> List[List[str]]:
    if not path.exists():
        raise LoadError(f"파일을 찾을 수 없습니다: {path}")
    if path.suffix.lower() == ".xls":
        raise LoadError(
            "구형 .xls 형식은 지원하지 않습니다. "
            "엑셀에서 '다른 이름으로 저장 → Excel 통합 문서(.xlsx)'로 변환해 주세요."
        )
    if is_excel:
        try:
            return read_excel_rows(path)
        except ExcelError as exc:
            raise LoadError(str(exc)) from exc
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.reader(f))
    except OSError as exc:
        raise LoadError(f"파일을 읽을 수 없습니다: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise LoadError(
            "CSV 인코딩을 해석할 수 없습니다. UTF-8(또는 엑셀의 'CSV UTF-8')로 "
            f"저장해 주세요: {exc}"
        ) from exc


def _trim_trailing_empty(row: List[str]) -> List[str]:
    end = len(row)
    while end > 0 and not row[end - 1].strip():
        end -= 1
    return row[:end]


def _normalize_widths(body: List[List[str]], width: int, lenient: bool) -> List[List[str]]:
    """행 폭을 헤더에 맞춘다. 엑셀은 뒤쪽 빈 셀이 생략되므로 관대하게 패딩한다."""
    normalized = []
    for i, row in enumerate(body):
        if lenient:
            row = _trim_trailing_empty(row)
            if len(row) > width:
                raise LoadError(
                    f"{i + 2}번째 행의 열 수({len(row)})가 헤더({width})보다 많습니다."
                )
            row = row + [""] * (width - len(row))
        elif len(row) != width:
            raise LoadError(
                f"{i + 2}번째 행의 열 수({len(row)})가 헤더({width})와 다릅니다."
            )
        normalized.append(row)
    return normalized


def _split_key(body: List[List[str]]):
    first_id = body[0][0].strip().lower() if body else ""
    if first_id in KEY_LABELS:
        key = [c.strip() for c in body[0][1:]]
        if any(k == "" for k in key):
            raise LoadError("정답 키 행에 빈 칸이 있습니다.")
        return key, body[1:]
    return None, body


def _norm(value: str) -> str:
    return value.strip().upper()


def _parse_binary(cell: str, row_i: int, col_j: int) -> int:
    if cell == "":
        return 0
    if cell in ("0", "1"):
        return int(cell)
    raise LoadError(
        f"{row_i + 2}번째 행 {col_j + 2}번째 열의 값 '{cell}'을 해석할 수 없습니다. "
        "원 응답 형식이면 헤더 아래에 KEY 행(정답 키)을 추가하세요."
    )
