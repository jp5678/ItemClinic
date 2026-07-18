"""분석 결과 JSON 직렬화 (CLI·웹 서버 공용)."""
from __future__ import annotations

import json

from .analyze import ExamResult
from .summary import SummaryExam


def diagnosis_json(result: ExamResult, exam_id: str) -> str:
    payload = {
        "exam_id": exam_id,
        "exam_type": result.profile.name,
        "n_students": result.n_students,
        "n_items": result.n_items,
        "kr20": round(result.kr20, 4),
        "mean_score": round(result.mean_score, 2),
        "sd_score": round(result.sd_score, 3),
        "items": [
            {
                "item_id": it.stats.item_id,
                "difficulty": round(it.stats.difficulty, 3),
                "point_biserial": round(it.stats.point_biserial, 3),
                "upper_lower": round(it.stats.upper_lower, 3),
                "kr20_if_deleted": round(it.stats.kr20_if_deleted, 4),
                "severity": it.diagnosis.severity.name,
                "flags": [f.message for f in it.diagnosis.flags],
                "icc": [round(g.proportion_correct, 3) for g in it.icc],
            }
            for it in result.items
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def summary_diagnosis_json(exam: SummaryExam, exam_id: str) -> str:
    meta = exam.meta
    payload = {
        "exam_id": exam_id,
        "exam_type": exam.profile.name,
        "format": "summary",
        "department": meta.department,
        "subject": meta.subject,
        "exam_date": meta.exam_date,
        "n_students": meta.n_students,
        "mean": meta.mean,
        "sd": meta.sd,
        "overall_p": meta.overall_p,
        "items": [
            {
                "number": it.item.number,
                "item_type": it.item.item_type,
                "key": it.item.key,
                "top_wrong": it.item.top_wrong,
                "difficulty": round(it.stats.difficulty, 3),
                "point_biserial": round(it.stats.point_biserial, 3),
                "difficulty_label": it.item.difficulty_label,
                "option_rates": {opt: round(rate, 3)
                                 for opt, rate in it.item.option_rates},
                "severity": it.diagnosis.severity.name,
                "flags": [f.message for f in it.diagnosis.flags],
            }
            for it in exam.items
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
