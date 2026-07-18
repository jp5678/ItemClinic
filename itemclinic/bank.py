"""문항은행: 시험별 문항 통계 이력을 JSON 파일에 누적한다.

같은 문항을 여러 학기에 출제하면 기록이 쌓여
난이도·변별도 추이를 추적하고, 조건 검색으로 재출제 후보를 고를 수 있다.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import List, Optional


class ItemBank:
    def __init__(self, path):
        self._path = Path(path)
        self._records: List[dict] = self._load()

    def _load(self) -> List[dict]:
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(
                f"문항은행 파일을 읽을 수 없습니다({self._path}): {exc}"
            ) from exc
        if not isinstance(data, list):
            raise ValueError(f"문항은행 파일 형식이 올바르지 않습니다: {self._path}")
        return data

    def add_record(
        self,
        exam_id: str,
        item_id: str,
        stats: dict,
        severity: str,
        text: Optional[dict],
        exam_type: Optional[str] = None,
    ) -> dict:
        """분석 결과 한 건을 추가하고 저장한다. 추가된 레코드를 반환한다."""
        record = {
            "exam_id": exam_id,
            "exam_type": exam_type,
            "item_id": item_id,
            "recorded_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "stats": dict(stats),
            "severity": severity,
            "text": text,
        }
        self._records = [*self._records, record]
        self._save()
        return record

    def all_records(self) -> List[dict]:
        return list(self._records)

    def search(
        self,
        severity: Optional[str] = None,
        min_difficulty: Optional[float] = None,
        max_difficulty: Optional[float] = None,
        min_discrimination: Optional[float] = None,
    ) -> List[dict]:
        """조건에 맞는 레코드를 반환한다. 조건이 None이면 무시한다."""
        def keep(r: dict) -> bool:
            s = r.get("stats", {})
            if severity is not None and r.get("severity") != severity:
                return False
            p = s.get("difficulty")
            if min_difficulty is not None and (p is None or p < min_difficulty):
                return False
            if max_difficulty is not None and (p is None or p > max_difficulty):
                return False
            d = s.get("point_biserial")
            if min_discrimination is not None and (d is None or d < min_discrimination):
                return False
            return True

        return [r for r in self._records if keep(r)]

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
