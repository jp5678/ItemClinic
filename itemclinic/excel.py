"""엑셀(.xlsx) 파일 읽기 — openpyxl 기반.

셀 값 정규화 규칙:
- 빈 셀(None) → ""
- 정수값 실수(1.0) → "1"  (엑셀은 숫자를 float로 저장하므로 응답 1~5 비교가 어긋나는 것 방지)
- 그 외 → 문자열로 변환 후 양끝 공백 제거
"""
from __future__ import annotations

from pathlib import Path
from typing import List


class ExcelError(ValueError):
    """엑셀 파일 형식/환경 오류."""


def read_excel_rows(path: Path) -> List[List[str]]:
    """첫 번째 워크시트의 모든 행을 문자열 행렬로 반환한다."""
    try:
        import openpyxl
    except ImportError as exc:
        raise ExcelError(
            "엑셀 파일을 읽으려면 openpyxl이 필요합니다. "
            "터미널에서 'pip3 install openpyxl'을 실행하거나 CSV로 저장해 업로드하세요."
        ) from exc
    try:
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        raise ExcelError(f"엑셀 파일을 열 수 없습니다({path.name}): {exc}") from exc
    try:
        sheet = workbook.worksheets[0]
        return [[_cell_to_str(v) for v in row] for row in sheet.iter_rows(values_only=True)]
    finally:
        workbook.close()


def _cell_to_str(value) -> str:
    import datetime

    if value is None:
        return ""
    if isinstance(value, datetime.datetime):
        return value.date().isoformat() if value.time() == datetime.time() else str(value)
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()
