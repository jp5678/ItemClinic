"""웹 UI 페이지 템플릿 — 학과 관리 시스템과 동일한 블루 팔레트."""
from __future__ import annotations

import datetime as _dt
import html

from .profiles import EXAM_TYPES

SEMESTERS = ("1학기", "2학기", "여름학기", "겨울학기")


def _default_semester(month: int) -> str:
    # 채점·분석은 학기말 직후에 몰리므로 2~7월은 1학기, 8~1월은 2학기를 기본으로 한다
    return "1학기" if 2 <= month <= 7 else "2학기"

PAGE_CSS = """
:root{--bg1:#cde1f3;--bg2:#e9f2fb;--card:#f7fbfe;--primary:#1e5b8d;
--primary-dark:#174a77;--text:#173f66;--muted:#5b7ea0;--border:#c9def0;
--soft:#e3eef9}
*{box-sizing:border-box}
body{font-family:'Apple SD Gothic Neo','Noto Sans KR',sans-serif;margin:0;
     min-height:100vh;display:flex;flex-direction:column;color:var(--text);
     background:radial-gradient(1000px 600px at 15% 10%,var(--bg2),transparent 60%),
                radial-gradient(900px 700px at 90% 90%,var(--bg2),transparent 55%),
                var(--bg1)}
main{flex:1;display:flex;align-items:center;justify-content:center;padding:40px 16px}
.card{background:var(--card);border-radius:22px;padding:40px 44px;width:100%;
      max-width:480px;box-shadow:0 18px 50px rgba(23,74,119,.18)}
.icon{width:76px;height:76px;margin:0 auto 18px;border-radius:20px;
      background:linear-gradient(160deg,#2e7cb8,#1b5a8c);display:flex;
      align-items:center;justify-content:center;
      box-shadow:0 8px 20px rgba(23,74,119,.25),0 0 0 8px #e9f2fb}
h1{font-size:1.45rem;text-align:center;margin:0 0 6px;color:var(--primary-dark)}
.sub{text-align:center;color:var(--muted);font-size:.92rem;margin:0 0 26px}
label{display:block;font-weight:700;font-size:.92rem;margin:16px 0 6px}
input[type=text],select{width:100%;padding:12px 14px;border:1px solid var(--border);
      border-radius:10px;font-size:1rem;background:#fff;color:var(--text)}
input[type=file]{width:100%;padding:10px;border:1px dashed var(--border);
      border-radius:10px;background:#fff;font-size:.9rem}
button{width:100%;margin-top:26px;padding:15px;border:none;border-radius:12px;
      background:var(--primary);color:#fff;font-size:1.1rem;font-weight:700;
      cursor:pointer}
button:hover{background:var(--primary-dark)}
.hint{color:var(--muted);font-size:.8rem;margin:4px 0 0}
.row2{display:flex;gap:12px}
.row2>div{flex:1}
footer{background:var(--soft);color:var(--primary);text-align:center;
      padding:12px;font-size:.9rem}
.error{background:#faeceb;border:1px solid #e5b6b3;border-radius:10px;
      padding:14px 16px;margin-bottom:8px;font-size:.95rem}
a{color:var(--primary)}
"""

ICON_SVG = (
    '<svg width="38" height="38" viewBox="0 0 24 24" fill="none" '
    'stroke="#fff" stroke-width="2" stroke-linecap="round">'
    '<path d="M4 20V10M10 20V4M16 20v-8M22 20H2"/></svg>'
)


def upload_page(footer: str) -> str:
    now = _dt.date.today()
    type_options = "".join(
        f'<option value="{html.escape(name)}">{html.escape(name)} — '
        f'{html.escape(p.description)}</option>'
        for name, p in EXAM_TYPES.items()
    )
    year_options = "".join(
        f'<option value="{y}"{" selected" if y == now.year else ""}>{y}학년도</option>'
        for y in range(now.year - 2, now.year + 2)
    )
    default_sem = _default_semester(now.month)
    semester_options = "".join(
        f'<option value="{s}"{" selected" if s == default_sem else ""}>{s}</option>'
        for s in SEMESTERS
    )
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ItemClinic — 문항분석</title><style>{PAGE_CSS}</style></head>
<body><main><div class="card">
<div class="icon">{ICON_SVG}</div>
<h1>문항분석 업로드</h1>
<p class="sub">시험 결과 자동 분석 및 불량문항 진단 시스템</p>
<form action="/analyze" method="post" enctype="multipart/form-data">
<div class="row2">
<div><label>학년도</label>
<select name="year">{year_options}</select></div>
<div><label>학기</label>
<select name="semester">{semester_options}</select></div>
</div>
<label>시험 유형</label>
<select name="exam_type">{type_options}</select>
<label>시험 이름 <span class="hint">(과목명 등 — 학년도·학기가 자동으로 앞에 붙습니다)</span></label>
<input type="text" name="exam_id" placeholder="예: 성인간호학 중간고사">
<label>과목명 <span class="hint">(선택 — 개선 문항 생성에 사용)</span></label>
<input type="text" name="subject" placeholder="예: 성인간호학">
<label>응답 파일 (CSV 또는 엑셀)</label>
<input type="file" name="csv" accept=".csv,.xlsx,.xlsm" required>
<p class="hint">KEY 행 + 원 응답(A~E) 또는 0/1 채점 행렬 · 빈 셀은 오답 처리</p>
<label>상단 제외 행 수 <span class="hint">(CSV·엑셀 공통 — 1~7행 제목 영역이면 7)</span></label>
<input type="text" name="skip_rows" value="7" inputmode="numeric">
<p class="hint">1~7행은 제목 영역으로 제외되고 8행(헤더)부터 읽습니다 ·
파일 1행부터 데이터가 시작하면 0으로 바꾸세요</p>
<label>문항 원문 JSON <span class="hint">(선택)</span></label>
<input type="file" name="items" accept=".json">
<label>Claude API 키 <span class="hint">(선택)</span></label>
<input type="password" name="api_key" autocomplete="off"
       placeholder="sk-ant-... (입력 시 개선 문항 자동 생성)">
<p class="hint">입력하면 불량문항 개선안이 리포트에 바로 포함됩니다 ·
미입력 시 개선 프롬프트 복사 방식 · 키는 이 브라우저(localStorage)에만 저장되며
서버나 파일에는 남지 않습니다 · 비우고 제출하면 저장된 키도 삭제됩니다</p>
<button type="submit">분석 시작</button>
</form>
</div></main>
<footer>{html.escape(footer)}</footer>
<script>
(function () {{
  var field = document.querySelector('input[name=api_key]');
  if (!field) return;
  try {{ field.value = localStorage.getItem('itemclinic_api_key') || ''; }} catch (e) {{}}
  document.querySelector('form').addEventListener('submit', function () {{
    try {{
      var value = field.value.trim();
      if (value) localStorage.setItem('itemclinic_api_key', value);
      else localStorage.removeItem('itemclinic_api_key');
    }} catch (e) {{}}
  }});
}})();
</script></body></html>"""


def error_page(message: str, footer: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ItemClinic — 오류</title><style>{PAGE_CSS}</style></head>
<body><main><div class="card">
<div class="icon">{ICON_SVG}</div>
<h1>분석 오류</h1>
<div class="error">{html.escape(message)}</div>
<p><a href="/">← 업로드 화면으로 돌아가기</a></p>
</div></main>
<footer>{html.escape(footer)}</footer></body></html>"""


COPY_ICON_SVG = (
    '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true">'
    '<rect x="9" y="9" width="13" height="13" rx="2"/>'
    '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>'
)

COPY_SCRIPT = """<script>
function icCopy(button, targetId) {
  var text = document.getElementById(targetId).textContent;
  var done = function () {
    button.classList.add('done');
    button.innerHTML = '\\u2713';
    setTimeout(function () {
      button.classList.remove('done');
      button.innerHTML = button.dataset.icon;
    }, 1500);
  };
  var fallback = function () {
    var area = document.createElement('textarea');
    area.value = text;
    document.body.appendChild(area);
    area.select();
    document.execCommand('copy');
    document.body.removeChild(area);
    done();
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done).catch(fallback);
  } else {
    fallback();
  }
}
document.querySelectorAll('.copy-btn').forEach(function (button) {
  button.dataset.icon = button.innerHTML;
  button.addEventListener('click', function () {
    icCopy(button, button.getAttribute('data-target'));
  });
});
</script>"""


def _copy_button(target_id: str, label: str) -> str:
    return (f'<button type="button" class="copy-btn" data-target="{target_id}" '
            f'title="{label} 복사" aria-label="{label} 복사">{COPY_ICON_SVG}</button>')


def report_extras(
    prompt: str,
    diagnosis_json: str,
    out_dir: str,
    improved: str = "",
    improve_error: str = "",
) -> str:
    """리포트 하단에 붙는 개선안/프롬프트/JSON 섹션 (복사 버튼 포함)."""
    improved_html = ""
    if improved:
        improved_html = f"""
<h2>Claude 개선안 {_copy_button("ic-improved", "개선안")}</h2>
<div class="item"><p class="meta">API로 자동 생성된 원인 해석과 대체 문항 초안입니다.
(저장 위치: {html.escape(out_dir)}/improved_items.md)</p>
<details open><summary>접기 / 펼치기</summary>
<pre id="ic-improved" style="white-space:pre-wrap;font-size:.85rem">{html.escape(improved)}</pre>
</details></div>"""
    elif improve_error:
        improved_html = f"""
<h2>Claude 개선안</h2>
<div class="item"><div class="flag warn">자동 생성에 실패했습니다: {html.escape(improve_error)}
아래 개선 프롬프트를 복사해 Claude에 직접 붙여넣어 주세요.</div></div>"""
    return f"""
{improved_html}
<h2>개선 프롬프트 {_copy_button("ic-prompt", "개선 프롬프트")}</h2>
<div class="item"><p class="meta">아래 내용을 Claude에 붙여넣으면 원인 해석과
대체 문항 초안을 받을 수 있습니다. (저장 위치: {html.escape(out_dir)})</p>
<details><summary>펼쳐 보기</summary>
<pre id="ic-prompt" style="white-space:pre-wrap;font-size:.85rem">{html.escape(prompt)}</pre>
</details></div>
<h2>진단 데이터 (JSON) {_copy_button("ic-json", "진단 데이터")}</h2>
<div class="item"><details><summary>펼쳐 보기</summary>
<pre id="ic-json" style="white-space:pre-wrap;font-size:.8rem">{html.escape(diagnosis_json)}</pre>
</details></div>
<p style="text-align:center;margin-top:28px">
<a href="/" style="font-weight:700">← 새 분석 시작</a></p>
{COPY_SCRIPT}
"""
