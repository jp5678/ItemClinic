"""명령행 인터페이스.

사용 예:
  python -m itemclinic analyze 결과.csv --exam-id 2026-1-중간 --items 문항.json
  python -m itemclinic bank-search --severity CRITICAL
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analyze import analyze_exam
from .bank import ItemBank
from .diagnose import Severity
from .improve import (build_prompt, build_summary_prompt,
                      generate_improvements, select_flagged)
from .intake import load_any
from .loader import LoadError
from .profiles import EXAM_TYPES, get_profile
from .report import render_report
from .serialize import diagnosis_json, summary_diagnosis_json
from .summary_report import render_summary_report

DEFAULT_BANK = "item_bank.json"


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (LoadError, ValueError, RuntimeError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="itemclinic", description="문항분석 자동화 파이프라인")
    sub = parser.add_subparsers(required=True)

    a = sub.add_parser("analyze", help="CSV/엑셀 분석 → 리포트/진단/개선 프롬프트 생성")
    a.add_argument("csv", help="응답 파일 CSV/엑셀(.xlsx) — KEY 행 포함 원응답 또는 0/1 행렬")
    a.add_argument("--skip-rows", type=int, default=0,
                   help="파일 상단 제목 영역 행 수 (해당 행들은 제외, 기본: 0)")
    a.add_argument("--exam-id", default=None, help="시험 식별자 (기본: 파일명)")
    a.add_argument("--exam-type", default="일반", choices=list(EXAM_TYPES),
                   help="시험 유형 — 유형별로 진단 기준이 달라집니다 (기본: 일반)")
    a.add_argument("--subject", default=None, help="과목명 (개선 프롬프트에 사용)")
    a.add_argument("--items", default=None, help="문항 원문 JSON (선택)")
    a.add_argument("--out", default=None, help="출력 디렉토리 (기본: CSV 옆 <exam-id>_analysis)")
    a.add_argument("--bank", default=DEFAULT_BANK, help=f"문항은행 파일 (기본: {DEFAULT_BANK})")
    a.add_argument("--no-llm", action="store_true", help="Claude API 호출 생략(프롬프트 파일만 생성)")
    a.set_defaults(func=cmd_analyze)

    b = sub.add_parser("bank-search", help="문항은행 조건 검색")
    b.add_argument("--bank", default=DEFAULT_BANK)
    b.add_argument("--severity", choices=["OK", "WARNING", "CRITICAL"], default=None)
    b.add_argument("--min-p", type=float, default=None, help="최소 난이도")
    b.add_argument("--max-p", type=float, default=None, help="최대 난이도")
    b.add_argument("--min-r", type=float, default=None, help="최소 변별도")
    b.set_defaults(func=cmd_bank_search)

    s = sub.add_parser("serve", help="브라우저 업로드 UI 서버 실행")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--out", default="web_analyses", help="분석 결과 저장 디렉토리")
    s.add_argument("--bank", default=DEFAULT_BANK)
    s.add_argument("--footer", default=None, help="화면 하단 문구 (예: 학과·이름)")
    s.set_defaults(func=cmd_serve)
    return parser


def cmd_serve(args) -> int:
    from .server import DEFAULT_FOOTER, run_server

    run_server(args.port, Path(args.out), Path(args.bank),
               footer=args.footer or DEFAULT_FOOTER)
    return 0


def cmd_analyze(args) -> int:
    csv_path = Path(args.csv)
    profile = get_profile(args.exam_type)
    intake = load_any(csv_path, args.skip_rows, profile)
    if intake.kind == "summary":
        return _analyze_summary(args, csv_path, intake.summary)
    exam_id = args.exam_id or csv_path.stem
    result = analyze_exam(intake.responses, profile)
    item_texts = _load_item_texts(args.items)

    out_dir = Path(args.out) if args.out else csv_path.parent / f"{exam_id}_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    report_path = out_dir / "report.html"
    report_path.write_text(render_report(result, exam_id, item_texts=item_texts), encoding="utf-8")

    diag_path = out_dir / "diagnosis.json"
    diag_path.write_text(diagnosis_json(result, exam_id), encoding="utf-8")

    _update_bank(Path(args.bank), exam_id, result, item_texts)

    print(f"[검사] {args.exam_type} · N={result.n_students}, {result.n_items}문항, "
          f"KR-20={result.kr20:.3f}")
    _print_flag_summary(result)
    print(f"[출력] 리포트: {report_path}")
    print(f"[출력] 진단 JSON: {diag_path}")

    flagged = select_flagged(result.items)
    if flagged:
        _run_improvement(flagged, exam_id, args, item_texts, out_dir)
    else:
        print("[개선] 주의·불량 문항이 없어 개선안 생성을 건너뜁니다.")
    return 0


def _analyze_summary(args, csv_path: Path, exam) -> int:
    """문항 분석표(요약 형식): 파일 상단 텍스트를 시험 정보로 참조한다."""
    exam_id = args.exam_id or exam.meta.subject or csv_path.stem
    subject = args.subject or exam.meta.subject

    out_dir = Path(args.out) if args.out else csv_path.parent / f"{csv_path.stem}_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    diag = summary_diagnosis_json(exam, exam_id)
    (out_dir / "diagnosis.json").write_text(diag, encoding="utf-8")

    bank = ItemBank(Path(args.bank))
    for it in exam.items:
        bank.add_record(
            exam_id=exam_id,
            item_id=it.item.number,
            stats={"difficulty": round(it.stats.difficulty, 3),
                   "point_biserial": round(it.stats.point_biserial, 3)},
            severity=it.diagnosis.severity.name,
            text={"type": it.item.item_type, "key": it.item.key},
            exam_type=args.exam_type,
        )

    report_path = out_dir / "report.html"
    report_path.write_text(render_summary_report(exam, exam_id), encoding="utf-8")

    n = exam.meta.n_students
    print(f"[검사] {args.exam_type} · 문항 분석표(요약) · "
          f"{'N=' + str(n) + ', ' if n else ''}{len(exam.items)}문항")
    for it in exam.items:
        if it.diagnosis.severity == Severity.OK:
            continue
        label = "불량" if it.diagnosis.severity == Severity.CRITICAL else "주의"
        print(f"  - {it.item.number}번 [{label}] p={it.stats.difficulty:.2f}, "
              f"r={it.stats.point_biserial:.2f}")
    print(f"[출력] 리포트: {report_path}")
    print(f"[출력] 진단 JSON: {out_dir / 'diagnosis.json'}")

    flagged = [it for it in exam.items if it.diagnosis.severity >= Severity.WARNING]
    if flagged:
        prompt = build_summary_prompt(flagged, f"{exam_id} ({args.exam_type})", subject)
        prompt_path = out_dir / "improve_prompt.md"
        prompt_path.write_text(prompt, encoding="utf-8")
        print(f"[개선] 대상 {len(flagged)}문항, 프롬프트: {prompt_path}")
        if not args.no_llm:
            answer = generate_improvements(prompt)
            if answer is None:
                print("[개선] ANTHROPIC_API_KEY가 없어 자동 생성은 건너뜁니다.")
            else:
                (out_dir / "improved_items.md").write_text(answer, encoding="utf-8")
                print(f"[개선] Claude 개선안: {out_dir / 'improved_items.md'}")
    else:
        print("[개선] 주의·불량 문항이 없어 개선안 생성을 건너뜁니다.")
    return 0


def _print_flag_summary(result) -> None:
    for it in result.items:
        if it.diagnosis.severity == Severity.OK:
            continue
        label = "불량" if it.diagnosis.severity == Severity.CRITICAL else "주의"
        s = it.stats
        print(f"  - {s.item_id} [{label}] p={s.difficulty:.2f}, r={s.point_biserial:.2f}")


def _run_improvement(flagged, exam_id, args, item_texts, out_dir: Path) -> None:
    prompt = build_prompt(flagged, exam_id, args.subject, item_texts)
    prompt_path = out_dir / "improve_prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    print(f"[개선] 대상 {len(flagged)}문항, 프롬프트: {prompt_path}")

    if args.no_llm:
        return
    answer = generate_improvements(prompt)
    if answer is None:
        print("[개선] ANTHROPIC_API_KEY가 없어 자동 생성은 건너뜁니다. "
              "improve_prompt.md를 Claude에 붙여넣거나, Claude Code에서 "
              "'improve_prompt.md 읽고 개선안 작성해줘'라고 요청하세요.")
        return
    out_path = out_dir / "improved_items.md"
    out_path.write_text(answer, encoding="utf-8")
    print(f"[개선] Claude 개선안: {out_path}")


def _load_item_texts(path_str):
    if not path_str:
        return None
    path = Path(path_str)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"문항 원문 JSON을 읽을 수 없습니다({path}): {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("문항 원문 JSON은 {문항ID: {stem, options, objective}} 형식이어야 합니다.")
    return data


def _update_bank(bank_path: Path, exam_id: str, result, item_texts) -> None:
    bank = ItemBank(bank_path)
    for it in result.items:
        bank.add_record(
            exam_id=exam_id,
            item_id=it.stats.item_id,
            stats={
                "difficulty": round(it.stats.difficulty, 3),
                "point_biserial": round(it.stats.point_biserial, 3),
                "upper_lower": round(it.stats.upper_lower, 3),
            },
            severity=it.diagnosis.severity.name,
            text=(item_texts or {}).get(it.stats.item_id),
            exam_type=result.profile.name,
        )
    print(f"[은행] {result.n_items}문항 기록 누적: {bank_path}")


def cmd_bank_search(args) -> int:
    bank = ItemBank(Path(args.bank))
    hits = bank.search(
        severity=args.severity,
        min_difficulty=args.min_p,
        max_difficulty=args.max_p,
        min_discrimination=args.min_r,
    )
    if not hits:
        print("조건에 맞는 문항이 없습니다.")
        return 0
    for r in hits:
        s = r["stats"]
        print(f"{r['exam_id']} / {r['item_id']} [{r['severity']}] "
              f"p={s.get('difficulty')}, r={s.get('point_biserial')}")
    print(f"총 {len(hits)}건")
    return 0
