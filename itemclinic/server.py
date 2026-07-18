"""로컬 웹 서버: CSV 업로드 → 브라우저에서 바로 분석 리포트.

표준 라이브러리 http.server만 사용한다. 로컬 사용 전용(127.0.0.1 바인딩).
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from .analyze import analyze_exam
from .bank import ItemBank
from .diagnose import Severity
from .improve import (build_prompt, build_summary_prompt,
                      generate_improvements, select_flagged)
from .intake import load_any
from .loader import LoadError
from .multipart import MultipartError, parse_multipart
from .profiles import get_profile
from .report import FOOTER_TEXT, render_report
from .serialize import diagnosis_json, summary_diagnosis_json
from .summary_report import render_summary_report
from .webui import error_page, report_extras, upload_page

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
DEFAULT_FOOTER = FOOTER_TEXT
# 학교 시스템 출력물(CSV·엑셀 공통)은 1~7행이 제목 영역 → 업로드 기본 제외
DEFAULT_SKIP_ROWS = 7


def create_server(
    port: int,
    out_root,
    bank_path,
    footer: str = DEFAULT_FOOTER,
    host: str = "127.0.0.1",
) -> ThreadingHTTPServer:
    """설정이 주입된 HTTP 서버 인스턴스를 만든다 (serve_forever는 호출자 몫)."""
    config = {
        "out_root": Path(out_root),
        "bank_path": Path(bank_path),
        "footer": footer,
    }
    handler = type("ConfiguredHandler", (_Handler,), {"config": config})
    return ThreadingHTTPServer((host, port), handler)


class _Handler(BaseHTTPRequestHandler):
    config: dict = {}

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send_html(200, upload_page(self.config["footer"]))
        else:
            self._send_html(404, error_page("페이지를 찾을 수 없습니다.", self.config["footer"]))

    def do_POST(self):
        if self.path != "/analyze":
            self._send_html(404, error_page("페이지를 찾을 수 없습니다.", self.config["footer"]))
            return
        try:
            page = self._handle_analyze()
            self._send_html(200, page)
        except (LoadError, MultipartError, ValueError) as exc:
            self._send_html(400, error_page(f"오류: {exc}", self.config["footer"]))
        except Exception as exc:  # 예상 못한 오류도 사용자에게 알린다
            self._send_html(500, error_page(f"서버 내부 오류: {exc}", self.config["footer"]))

    def _handle_analyze(self) -> str:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            raise MultipartError("업로드된 파일이 없습니다.")
        if length > MAX_UPLOAD_BYTES:
            raise MultipartError("파일이 너무 큽니다 (최대 20MB).")
        body = self.rfile.read(length)
        parts = parse_multipart(body, self.headers.get("Content-Type", ""))

        csv_part = parts.get("csv")
        if csv_part is None or not csv_part.data.strip():
            raise LoadError("응답 파일(CSV 또는 엑셀)을 선택해 주세요.")
        exam_type = parts["exam_type"].value.strip() if "exam_type" in parts else "일반"
        exam_name = _field(parts, "exam_id")
        subject = _field(parts, "subject")
        term = _term_prefix(_field(parts, "year"), _field(parts, "semester"))
        # 시험 이름 = 학년도-학기 + 과목명 + 입력 이름 (과목명이 이름에 이미 있으면 중복 생략)
        name_parts = ([exam_name] if exam_name and subject and subject in exam_name
                      else [p for p in (subject, exam_name) if p])
        composed = f"{term} {' '.join(name_parts)}".strip() if name_parts else ""
        exam_id = _clean_exam_id(composed or "무제시험")
        skip_rows = _parse_skip_rows(parts.get("skip_rows"))
        item_texts = _parse_items(parts.get("items"))
        # API 키는 이 요청의 개선안 생성에만 쓰고 저장·로깅하지 않는다
        api_key = parts["api_key"].value.strip() if "api_key" in parts else ""

        out_dir = self._make_out_dir(exam_id)
        suffix = Path(csv_part.filename or "responses.csv").suffix.lower()
        if suffix not in (".csv", ".xlsx", ".xlsm", ".xls"):
            raise LoadError(f"지원하지 않는 파일 형식입니다({suffix or '확장자 없음'}). "
                            "CSV 또는 엑셀(.xlsx) 파일을 업로드하세요.")
        csv_path = out_dir / f"responses{suffix}"
        csv_path.write_bytes(csv_part.data)

        profile = get_profile(exam_type)
        intake = load_any(csv_path, skip_rows, profile)
        if intake.kind == "summary":
            return self._handle_summary(
                intake.summary, exam_id, exam_type, subject, out_dir, api_key,
                exam_id_given=bool(exam_name or subject),
            )
        result = analyze_exam(intake.responses, profile)

        diag = diagnosis_json(result, exam_id)
        (out_dir / "diagnosis.json").write_text(diag, encoding="utf-8")
        self._record_bank(exam_id, result, item_texts)

        flagged = select_flagged(result.items)
        prompt = ""
        if flagged:
            prompt = build_prompt(flagged, f"{exam_id} ({exam_type})",
                                  subject or None, item_texts)
            (out_dir / "improve_prompt.md").write_text(prompt, encoding="utf-8")

        improved, improve_error = self._maybe_generate(prompt, api_key, out_dir)
        extras = report_extras(prompt, diag, str(out_dir),
                               improved=improved, improve_error=improve_error) if prompt else (
            '<p class="meta" style="text-align:center">주의·불량 문항이 없어 '
            '개선 프롬프트를 생성하지 않았습니다. <a href="/">← 새 분석</a></p>'
        )
        page = render_report(result, exam_id, item_texts=item_texts, extra_html=extras)
        (out_dir / "report.html").write_text(page, encoding="utf-8")
        return page

    def _maybe_generate(self, prompt: str, api_key: str, out_dir: Path):
        """API 키가 주어진 경우에만 개선안을 생성한다. 실패해도 분석은 계속된다."""
        if not prompt or not api_key:
            return "", ""
        try:
            improved = generate_improvements(prompt, api_key=api_key)
        except RuntimeError as exc:
            return "", str(exc)
        if not improved:
            return "", "API 응답이 비어 있습니다."
        (out_dir / "improved_items.md").write_text(improved, encoding="utf-8")
        return improved, ""

    def _handle_summary(self, exam, exam_id, exam_type, subject, out_dir,
                        api_key: str, exam_id_given: bool) -> str:
        """문항 분석표(요약 형식) 처리: 파일 상단 텍스트를 시험 정보로 참조한다."""
        if not exam_id_given and exam.meta.subject:
            exam_id = exam.meta.subject
        subject = subject or exam.meta.subject or ""

        diag = summary_diagnosis_json(exam, exam_id)
        (out_dir / "diagnosis.json").write_text(diag, encoding="utf-8")

        bank = ItemBank(self.config["bank_path"])
        for it in exam.items:
            bank.add_record(
                exam_id=exam_id,
                item_id=it.item.number,
                stats={"difficulty": round(it.stats.difficulty, 3),
                       "point_biserial": round(it.stats.point_biserial, 3)},
                severity=it.diagnosis.severity.name,
                text={"type": it.item.item_type, "key": it.item.key},
                exam_type=exam_type,
            )

        flagged = [it for it in exam.items
                   if it.diagnosis.severity >= Severity.WARNING]
        prompt = ""
        if flagged:
            prompt = build_summary_prompt(flagged, f"{exam_id} ({exam_type})",
                                          subject or None)
            (out_dir / "improve_prompt.md").write_text(prompt, encoding="utf-8")

        improved, improve_error = self._maybe_generate(prompt, api_key, out_dir)
        extras = report_extras(prompt, diag, str(out_dir),
                               improved=improved, improve_error=improve_error) if prompt else (
            '<p class="meta" style="text-align:center">주의·불량 문항이 없어 '
            '개선 프롬프트를 생성하지 않았습니다. <a href="/">← 새 분석</a></p>'
        )
        page = render_summary_report(exam, exam_id, extra_html=extras)
        (out_dir / "report.html").write_text(page, encoding="utf-8")
        return page

    def _make_out_dir(self, exam_id: str) -> Path:
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        out_dir = self.config["out_root"] / f"{exam_id}_{stamp}"
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    def _record_bank(self, exam_id: str, result, item_texts) -> None:
        bank = ItemBank(self.config["bank_path"])
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

    def _send_html(self, status: int, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        print(f"[웹] {self.address_string()} - {fmt % args}")


def _field(parts, name: str) -> str:
    return parts[name].value.strip() if name in parts else ""


SEMESTER_SHORT = {"1학기": "1", "2학기": "2"}


def _term_prefix(year: str, semester: str) -> str:
    """학년도·학기 선택값을 '2026-1' 형태의 접두어로 만든다."""
    if not year:
        return ""
    short = SEMESTER_SHORT.get(semester, semester)
    return f"{year}-{short}" if short else year


def _clean_exam_id(raw: str) -> str:
    if not raw:
        raw = "무제시험"
    # 파일 경로에 안전한 이름으로 정리 (한글 유지)
    return re.sub(r'[\\/:*?"<>|\s]+', "-", raw)[:80]


def _parse_skip_rows(part) -> int:
    raw = part.value.strip() if part else ""
    if raw == "":
        return DEFAULT_SKIP_ROWS
    try:
        value = int(raw)
    except ValueError:
        raise LoadError(f"상단 제외 행 수는 숫자여야 합니다: '{raw}'") from None
    if value < 0:
        raise LoadError("상단 제외 행 수는 0 이상이어야 합니다.")
    return value


def _parse_items(part) -> Optional[dict]:
    if part is None or not part.data.strip():
        return None
    try:
        data = json.loads(part.data.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"문항 원문 JSON을 해석할 수 없습니다: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("문항 원문 JSON은 {문항ID: {stem, options}} 형식이어야 합니다.")
    return data


def run_server(port: int, out_root, bank_path, footer: str = DEFAULT_FOOTER) -> None:
    """서버를 기동하고 Ctrl+C까지 요청을 처리한다."""
    httpd = create_server(port, out_root, bank_path, footer)
    actual_port = httpd.server_address[1]
    print(f"[웹] ItemClinic 서버 시작: http://127.0.0.1:{actual_port}")
    print(f"[웹] 결과 저장 위치: {Path(out_root).resolve()}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[웹] 서버를 종료합니다.")
    finally:
        httpd.server_close()
