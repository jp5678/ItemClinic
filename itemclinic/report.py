"""한국어 HTML 분석 리포트 생성 (ICC SVG 내장, 단일 파일).

색상은 학과 관리 시스템과 동일한 블루 팔레트를 사용한다.
"""
from __future__ import annotations

import datetime as _dt
import html
from typing import Optional

from .analyze import ExamResult, ItemResult
from .diagnose import Severity
from .svg import icc_svg

SEVERITY_LABEL = {
    Severity.OK: ("정상", "#1e7a4f"),
    Severity.WARNING: ("주의", "#b97a1c"),
    Severity.CRITICAL: ("불량", "#c2403a"),
}

FOOTER_TEXT = ("ItemClinic — 문항은행 · 자동 문항분석 엔진 | "
               "청암대학교 간호학과 · 정종필 교수 · imjp5678@scjc.ac.kr")

# 첨부된 관리자 시스템과 동일한 블루 팔레트
CSS = """
:root{--bg1:#cde1f3;--bg2:#e9f2fb;--card:#f7fbfe;--primary:#1e5b8d;
--primary-dark:#174a77;--text:#173f66;--muted:#5b7ea0;--border:#c9def0;
--soft:#e3eef9}
body{font-family:'Apple SD Gothic Neo','Noto Sans KR',sans-serif;margin:0;
     background:radial-gradient(1000px 600px at 15% 10%,var(--bg2),transparent 60%),
                radial-gradient(900px 700px at 90% 90%,var(--bg2),transparent 55%),
                var(--bg1);
     color:var(--text);line-height:1.6;min-height:100vh}
.wrap{max-width:960px;margin:0 auto;padding:32px 20px 60px}
.hero{background:var(--card);border-radius:18px;padding:28px 32px;
      box-shadow:0 10px 30px rgba(23,74,119,.12);margin-bottom:24px}
h1{font-size:1.55rem;margin:0 0 4px;color:var(--primary-dark)}
.exam-name{font-size:1.05rem;font-weight:700;color:var(--primary);margin:0 0 4px}
h2{font-size:1.2rem;margin-top:36px;color:var(--primary-dark)}
.meta{color:var(--muted);font-size:.9rem}
.chip{display:inline-block;background:var(--soft);color:var(--primary);
      border:1px solid var(--border);border-radius:999px;padding:1px 12px;
      font-size:.8rem;font-weight:700;vertical-align:middle;margin-left:8px}
.cards{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0 6px}
.card{background:#fff;border:1px solid var(--border);border-radius:12px;
      padding:14px 18px;min-width:120px;box-shadow:0 3px 10px rgba(23,74,119,.06)}
.card .v{font-size:1.5rem;font-weight:700;color:var(--primary)}
.card .k{font-size:.8rem;color:var(--muted)}
table{border-collapse:collapse;width:100%;background:#fff;font-size:.9rem}
th,td{border:1px solid var(--border);padding:6px 10px;text-align:center}
th{background:var(--soft);color:var(--primary-dark)}
.item{background:var(--card);border:1px solid var(--border);border-radius:14px;
      padding:18px 22px;margin:16px 0;box-shadow:0 6px 18px rgba(23,74,119,.08)}
.item h3{margin:0 0 6px;color:var(--primary-dark)}
.badge{display:inline-block;border-radius:999px;color:#fff;
padding:2px 12px;font-size:.8rem;font-weight:700;margin-left:8px}
.flag{margin:8px 0;padding:10px 12px;border-radius:8px;background:#faeceb;font-size:.9rem}
.flag.warn{background:#faf3e3}
.flag.info{background:var(--soft)}
.copy-btn{display:inline-flex;align-items:center;justify-content:center;
  width:30px;height:30px;margin-left:10px;vertical-align:middle;cursor:pointer;
  border:1px solid var(--border);border-radius:8px;background:#fff;color:var(--primary)}
.copy-btn:hover{background:var(--soft)}
.copy-btn.done{color:#1e7a4f;border-color:#1e7a4f}
.row{display:flex;gap:20px;flex-wrap:wrap;align-items:flex-start}
.overflow{overflow-x:auto}
.keyrow{background:#e8f4ec;font-weight:700}
.footer{color:var(--muted);font-size:.85rem;text-align:center;margin-top:40px}
"""


def render_report(
    result: ExamResult,
    exam_id: str,
    generated_by: str = "ItemClinic",
    item_texts: Optional[dict] = None,
    extra_html: str = "",
) -> str:
    """분석 결과 전체를 단일 HTML 문자열로 렌더링한다."""
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    flagged = [it for it in result.items if it.diagnosis.severity != Severity.OK]
    sections = "".join(
        _item_section(it, (item_texts or {}).get(it.stats.item_id))
        for it in sorted(result.items, key=lambda i: -i.diagnosis.severity)
    )
    exam_type = result.profile.name
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ItemClinic 문항분석 리포트</title><style>{CSS}</style></head>
<body><div class="wrap">
<div class="hero">
<h1>문항분석 리포트
<span class="chip">{html.escape(exam_type)}</span></h1>
<p class="exam-name">{html.escape(exam_id)}</p>
<p class="meta">{generated_by} · 생성 {now} · N={result.n_students}, {result.n_items}문항
· 진단 기준: {html.escape(result.profile.description)}</p>
<div class="cards">
  <div class="card"><div class="v">{result.kr20:.3f}</div><div class="k">KR-20 신뢰도</div></div>
  <div class="card"><div class="v">{result.mean_score:.1f}</div><div class="k">평균 점수</div></div>
  <div class="card"><div class="v">{result.sd_score:.2f}</div><div class="k">표준편차</div></div>
  <div class="card"><div class="v">{len(flagged)}</div><div class="k">주의·불량 문항 수</div></div>
</div>
{_kr20_comment(result)}
</div>
<h2>문항 통계 요약</h2>
<div class="overflow">{_summary_table(result)}</div>
<h2>문항별 상세 진단</h2>
{sections}
{extra_html}
<p class="footer">{html.escape(FOOTER_TEXT)}</p>
</div></body></html>"""


def _kr20_comment(result: ExamResult) -> str:
    value = result.kr20
    if result.profile.criterion_referenced:
        msg = ("준거참조 검사(진단·형성평가)에서는 학생 점수가 비슷할수록 KR-20이 "
               "낮게 나오는 것이 자연스럽습니다. 신뢰도 수치보다 문항별 도달률과 "
               "음의 변별도 문항 유무를 중심으로 해석하세요.")
    elif value >= 0.8:
        msg = "학급 단위 의사결정에 충분한 신뢰도입니다."
    elif value >= 0.7:
        msg = "수용 가능한 수준이나, 불량 문항 개선 시 더 올릴 수 있습니다."
    else:
        msg = ("낮은 수준입니다. 아래 불량 문항을 수정·삭제하면 개선 여지가 큽니다. "
               "(문항 수가 적을수록 KR-20은 낮게 나오는 점도 감안하세요.)")
    return f'<p class="meta">KR-20 해석: {msg}</p>'


def _summary_table(result: ExamResult) -> str:
    rows = []
    for it in result.items:
        s = it.stats
        label, color = SEVERITY_LABEL[it.diagnosis.severity]
        rows.append(
            f"<tr><td>{html.escape(s.item_id)}</td><td>{s.difficulty:.2f}</td>"
            f"<td>{s.point_biserial:.2f}</td><td>{s.upper_lower:.2f}</td>"
            f"<td>{s.kr20_if_deleted:.3f}</td>"
            f'<td style="color:{color};font-weight:700">{label}</td></tr>'
        )
    return (
        "<table><thead><tr><th>문항</th><th>난이도 p</th><th>변별도 r<sub>pb</sub></th>"
        "<th>상하위 D</th><th>삭제 시 KR-20</th><th>판정</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _item_section(it: ItemResult, text: Optional[dict]) -> str:
    s = it.stats
    label, color = SEVERITY_LABEL[it.diagnosis.severity]
    line_color = {"정상": "#1e5b8d", "주의": "#b97a1c", "불량": "#c2403a"}[label]
    flags = "".join(
        f'<div class="flag{" warn" if f.severity == Severity.WARNING else ""}">{html.escape(f.message)}</div>'
        for f in it.diagnosis.flags
    ) or '<p class="meta">특이사항 없음.</p>'
    stem = ""
    if text and text.get("stem"):
        stem = f'<p class="meta">문항: {html.escape(str(text["stem"]))}</p>'
    return f"""<div class="item" id="{html.escape(s.item_id)}">
<h3>{html.escape(s.item_id)}
<span class="badge" style="background:{color}">{label}</span></h3>
{stem}
<p class="meta">난이도 p={s.difficulty:.2f} · 변별도 r={s.point_biserial:.2f} ·
상하위 D={s.upper_lower:.2f} · 삭제 시 KR-20={s.kr20_if_deleted:.3f}</p>
{flags}
<div class="row"><div>{icc_svg(it.icc, line_color)}</div>{_distractor_table(it)}</div>
</div>"""


def _distractor_table(it: ItemResult) -> str:
    if not it.distractors:
        return ""
    rows = "".join(
        f'<tr class="{"keyrow" if o.is_key else ""}">'
        f"<td>{html.escape(o.option)}{' ✓' if o.is_key else ''}</td>"
        f"<td>{o.overall_rate:.0%}</td><td>{o.upper_rate:.0%}</td>"
        f"<td>{o.lower_rate:.0%}</td></tr>"
        for o in it.distractors
    )
    return (
        '<div class="overflow"><table><thead><tr><th>선택지</th><th>전체</th>'
        "<th>상위 27%</th><th>하위 27%</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
    )
