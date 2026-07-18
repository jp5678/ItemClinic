"""불량문항 개선안 생성.

ANTHROPIC_API_KEY와 anthropic 패키지가 있으면 Claude API로
원인 해석 + 대체 문항 초안을 자동 생성하고,
없으면 동일한 내용의 프롬프트 파일(improve_prompt.md)을 만들어
Claude 앱/Claude Code에 붙여넣어 쓸 수 있게 한다.
"""
from __future__ import annotations

import os
from typing import Optional, Sequence

from .analyze import ItemResult
from .diagnose import Severity

DEFAULT_MODEL = "claude-sonnet-5"
MAX_TOKENS = 4000


def build_prompt(
    flagged: Sequence[ItemResult],
    exam_id: str,
    subject: Optional[str],
    item_texts: Optional[dict],
) -> str:
    """진단 결과를 담은 문항 개선 요청 프롬프트(한국어)를 만든다."""
    if not flagged:
        raise ValueError("개선 대상 문항이 없습니다.")
    blocks = "\n\n".join(_item_block(it, item_texts) for it in flagged)
    subject_line = f"과목: {subject}\n" if subject else ""
    return f"""당신은 교육측정 전문가이자 해당 과목의 출제위원입니다.
아래는 시험 "{exam_id}"에서 통계적으로 불량 판정을 받은 객관식 문항들의 분석 결과입니다.
{subject_line}
각 문항에 대해 다음을 수행하세요.

1. **원인 진단**: 통계 패턴(난이도, 변별도, 상하위 집단의 선택지 분포, ICC 형태)을 근거로
   왜 이 문항이 불량인지 해석하세요. (정답 오류 의심 / 중의적 표현 / 상위권을 속이는 오답 /
   수업에서 다루지 않은 내용 / 단서 노출 등 구체적 가설 제시)
2. **수정안**: 원래 문항의 취지를 살린 최소 수정안 1개.
3. **대체 문항**: 같은 학습목표를 재는 새 문항 1개 (문두 + 선택지 4~5개 + 정답 + 해설).
4. **오답지 설계 근거**: 각 오답이 어떤 오개념을 잡아내는지 한 줄씩.

목표 통계치: 난이도 0.4~0.7, 변별도(양류상관) 0.30 이상.
문항 원문이 제공되지 않은 경우, 통계 해석과 함께 원문 확인이 필요한 체크리스트를 제시하세요.

---

{blocks}
"""


def _item_block(it: ItemResult, item_texts: Optional[dict]) -> str:
    s = it.stats
    lines = [f"### 문항 {s.item_id}"]
    text = (item_texts or {}).get(s.item_id)
    if text:
        lines.append(f"문두: {text.get('stem', '(미제공)')}")
        for opt, body in (text.get("options") or {}).items():
            lines.append(f"  {opt}. {body}")
        if text.get("objective"):
            lines.append(f"학습목표: {text['objective']}")
    else:
        lines.append("문항 원문: (미제공 — 통계만으로 진단)")
    lines.append(
        f"통계: 난이도 p={s.difficulty:.2f}, 변별도 r_pb={s.point_biserial:.2f}, "
        f"상하위27% D={s.upper_lower:.2f}, 삭제 시 KR-20={s.kr20_if_deleted:.3f}"
    )
    icc = " → ".join(f"{g.proportion_correct:.0%}" for g in it.icc)
    lines.append(f"ICC(하위→상위 그룹 정답률): {icc}")
    if it.distractors:
        lines.append("선택지 분포 (전체 / 상위27% / 하위27%):")
        for o in it.distractors:
            mark = " (정답)" if o.is_key else ""
            lines.append(
                f"  {o.option}{mark}: {o.overall_rate:.0%} / {o.upper_rate:.0%} / {o.lower_rate:.0%}"
            )
    lines.append("진단 플래그:")
    for f in it.diagnosis.flags:
        lines.append(f"  - {f.message}")
    return "\n".join(lines)


def build_summary_prompt(flagged, exam_label: str, subject: Optional[str]) -> str:
    """문항 분석표(요약 형식) 기반 개선 요청 프롬프트."""
    if not flagged:
        raise ValueError("개선 대상 문항이 없습니다.")
    blocks = "\n\n".join(_summary_block(it) for it in flagged)
    subject_line = f"과목: {subject}\n" if subject else ""
    return f"""당신은 교육측정 전문가이자 해당 과목의 출제위원입니다.
아래는 시험 "{exam_label}"의 문항 분석표에서 불량 판정을 받은 객관식 문항들입니다.
{subject_line}
각 문항에 대해 다음을 수행하세요.

1. **원인 진단**: 정답률·변별도·답지반응률 분포를 근거로 왜 불량인지 해석하세요.
   (정답 오류 의심 / 중의적 표현 / 상위권을 속이는 오답 / 기능하지 않는 오답지 등)
2. **수정안**: 문항 유형(학습목표)을 유지한 최소 수정 방향 제안.
3. **대체 문항**: 같은 유형을 재는 새 문항 1개 (문두 + 선택지 5개 + 정답 + 해설).
4. **오답지 설계 근거**: 각 오답이 어떤 오개념을 잡아내는지 한 줄씩.

목표 통계치: 난이도 0.4~0.7, 변별도 0.30 이상, 모든 오답지 선택률 5% 이상.
문항 원문이 없으므로 '유형' 텍스트를 학습목표로 삼아 출제하고,
원문 확인이 필요한 사항은 체크리스트로 제시하세요.

---

{blocks}
"""


def _summary_block(it) -> str:
    item = it.item
    lines = [f"### 문항 {item.number}"]
    if item.item_type:
        lines.append(f"유형(학습목표): {item.item_type}")
    lines.append(
        f"통계: 정답률 p={it.stats.difficulty:.2f}, 변별도 r={it.stats.point_biserial:.2f}, "
        f"난이도 표기={item.difficulty_label or '-'}"
    )
    lines.append(f"정답: {item.key or '-'}번, 최다오답: {item.top_wrong or '-'}번")
    if item.option_rates:
        rates = ", ".join(f"{opt}번 {rate:.0%}" for opt, rate in item.option_rates)
        lines.append(f"답지반응률: {rates}")
    lines.append("진단 플래그:")
    for f in it.diagnosis.flags:
        lines.append(f"  - {f.message}")
    return "\n".join(lines)


def generate_improvements(
    prompt: str,
    model: str = DEFAULT_MODEL,
    api_key: Optional[str] = None,
) -> Optional[str]:
    """Claude API 호출로 개선안을 생성한다.

    api_key를 직접 주면 그것을 쓰고(웹 업로드 경로), 없으면 ANTHROPIC_API_KEY
    환경변수를 쓴다. 키가 아예 없으면 None을 반환해 프롬프트 파일로 대체한다.
    키는 이 호출에만 쓰이며 저장하지 않는다.
    """
    explicit_key = bool(api_key)
    if not api_key and not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        if explicit_key:
            raise RuntimeError(
                "anthropic 패키지가 설치되어 있지 않습니다. 터미널에서 "
                "'pip3 install anthropic' 실행 후 다시 시도하세요."
            ) from None
        return None
    try:
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
    except Exception as exc:  # API 오류는 폴백으로 처리하되 사유를 남긴다
        raise RuntimeError(f"Claude API 호출에 실패했습니다: {exc}") from exc


def select_flagged(items: Sequence[ItemResult], min_severity: Severity = Severity.WARNING):
    """개선 대상(주의 이상) 문항을 심각도 내림차순으로 반환한다."""
    return tuple(sorted(
        (it for it in items if it.diagnosis.severity >= min_severity),
        key=lambda it: -it.diagnosis.severity,
    ))
