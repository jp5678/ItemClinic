"""문항 분석표(요약 형식) 전용 HTML 리포트."""
from __future__ import annotations

import datetime as _dt
import html

from .diagnose import Severity
from .report import CSS, FOOTER_TEXT, SEVERITY_LABEL
from .summary import SummaryExam, SummaryItemResult


def render_summary_report(exam: SummaryExam, exam_id: str, extra_html: str = "") -> str:
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    meta = exam.meta
    flagged = [it for it in exam.items if it.diagnosis.severity != Severity.OK]
    meta_bits = [b for b in (
        meta.department, meta.subject,
        f"시험일 {meta.exam_date}" if meta.exam_date else None,
    ) if b]
    sections = "".join(
        _item_section(it)
        for it in sorted(exam.items, key=lambda i: -i.diagnosis.severity)
    )
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ItemClinic 문항분석 리포트</title><style>{CSS}</style></head>
<body><div class="wrap">
<div class="hero">
<h1>문항분석 리포트
<span class="chip">{html.escape(exam.profile.name)}</span>
<span class="chip">문항 분석표(요약)</span></h1>
<p class="exam-name">{html.escape(exam_id)}</p>
<p class="meta">ItemClinic · 생성 {now} · {html.escape(' · '.join(meta_bits))}</p>
<div class="cards">
  {_card(meta.n_students, "응시인원")}
  {_card(meta.mean, "전체평균")}
  {_card(meta.sd, "표준편차")}
  {_card(f"{meta.overall_p:.1%}" if meta.overall_p is not None else None, "전체 정답률")}
  {_card(len(flagged), "주의·불량 문항 수")}
</div>
<p class="meta">이 파일은 학생별 원 응답이 아닌 <b>요약 분석표</b>이므로 KR-20 신뢰도와
문항특성곡선(ICC)은 산출하지 않습니다. 표에 제공된 정답률·변별도·답지반응률을
기준으로 진단합니다.</p>
</div>
<h2>문항 통계 요약</h2>
<div class="overflow">{_summary_table(exam)}</div>
<h2>문항별 상세 진단</h2>
{sections}
{extra_html}
<p class="footer">{html.escape(FOOTER_TEXT)}</p>
</div></body></html>"""


def _card(value, label: str) -> str:
    if value is None:
        return ""
    return (f'<div class="card"><div class="v">{html.escape(str(value))}</div>'
            f'<div class="k">{label}</div></div>')


def _summary_table(exam: SummaryExam) -> str:
    rows = []
    for it in exam.items:
        label, color = SEVERITY_LABEL[it.diagnosis.severity]
        item = it.item
        rows.append(
            f"<tr><td>{html.escape(item.number)}</td>"
            f'<td style="text-align:left">{html.escape(item.item_type or "-")}</td>'
            f"<td>{html.escape(item.key or '-')}</td>"
            f"<td>{it.stats.difficulty:.2f}</td>"
            f"<td>{it.stats.point_biserial:.2f}</td>"
            f"<td>{html.escape(item.difficulty_label or '-')}</td>"
            f'<td style="color:{color};font-weight:700">{label}</td></tr>'
        )
    return (
        "<table><thead><tr><th>문항</th><th>유형</th><th>정답</th>"
        "<th>정답률 p</th><th>변별도</th><th>난이도</th><th>판정</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _item_section(it: SummaryItemResult) -> str:
    item = it.item
    label, color = SEVERITY_LABEL[it.diagnosis.severity]
    css_class = {Severity.CRITICAL: "", Severity.WARNING: " warn", Severity.OK: " info"}
    flags = "".join(
        f'<div class="flag{css_class[f.severity]}">{html.escape(f.message)}</div>'
        for f in it.diagnosis.flags
    ) or '<p class="meta">특이사항 없음.</p>'
    type_line = (f'<p class="meta">유형: {html.escape(item.item_type)}</p>'
                 if item.item_type else "")
    return f"""<div class="item" id="item-{html.escape(item.number)}">
<h3>{html.escape(item.number)}번 문항
<span class="badge" style="background:{color}">{label}</span></h3>
{type_line}
<p class="meta">정답 {html.escape(item.key or '-')}번 · 정답률 p={it.stats.difficulty:.2f}
· 변별도 r={it.stats.point_biserial:.2f}
· 난이도 {html.escape(item.difficulty_label or '-')}
· 최다오답 {html.escape(item.top_wrong or '-')}번</p>
{flags}
{_rates_table(it)}
</div>"""


def _rates_table(it: SummaryItemResult) -> str:
    if not it.item.option_rates:
        return ""
    key = (it.item.key or "").strip()
    rows = []
    for opt, rate in it.item.option_rates:
        is_key = opt == key
        bar_color = "#1e5b8d" if is_key else "#b6cde4"
        rows.append(
            f'<tr class="{"keyrow" if is_key else ""}">'
            f"<td>{html.escape(opt)}{' ✓' if is_key else ''}</td>"
            f"<td>{rate:.1%}</td>"
            f'<td style="text-align:left;min-width:180px"><div style="background:{bar_color};'
            f'height:12px;border-radius:6px;width:{max(rate * 100, 1):.0f}%"></div></td></tr>'
        )
    return (
        '<div class="overflow"><table><thead><tr><th>선택지</th><th>반응률</th>'
        "<th>분포</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )
