"""웹 서버 통합 테스트: 업로드 페이지 + 분석 요청."""
import http.client
import threading

import pytest

from itemclinic.server import create_server

BOUNDARY = "----TestBoundary"
CSV_CONTENT = (
    "student,Q1,Q2,Q3,Q4\nKEY,A,B,C,D\n"
    + "\n".join(f"u{i},A,B,C,A" for i in range(6))
    + "\n" + "\n".join(f"l{i},B,C,D,D" for i in range(6))
)


@pytest.fixture
def server(tmp_path):
    httpd = create_server(
        port=0,
        out_root=tmp_path / "out",
        bank_path=tmp_path / "bank.json",
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()


def multipart_body(fields, files):
    chunks = []
    for name, value in fields.items():
        chunks.append(
            f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode()
        )
    for name, (filename, data) in files.items():
        chunks.append(
            f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="{name}"; '
            f'filename="{filename}"\r\n\r\n'.encode() + data + b"\r\n"
        )
    chunks.append(f"--{BOUNDARY}--\r\n".encode())
    return b"".join(chunks)


def request(httpd, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
    conn.request(method, path, body=body, headers=headers or {})
    response = conn.getresponse()
    data = response.read()
    conn.close()
    return response.status, data.decode("utf-8", errors="replace")


class TestServer:
    def test_upload_page(self, server):
        status, body = request(server, "GET", "/")
        assert status == 200
        assert "문항분석" in body
        assert "진단평가" in body and "기말고사" in body

    def test_upload_page_has_term_dropdowns(self, server):
        status, body = request(server, "GET", "/")
        assert status == 200
        assert 'name="year"' in body and "학년도</option>" in body
        assert 'name="semester"' in body
        for sem in ("1학기", "2학기", "여름학기", "겨울학기"):
            assert sem in body

    def test_term_prefix_composed_into_exam_id(self, server, tmp_path):
        body = multipart_body(
            {"exam_id": "성인간호학 중간고사", "year": "2026", "semester": "1학기",
             "exam_type": "중간고사", "subject": "", "skip_rows": "0"},
            {"csv": ("r.csv", CSV_CONTENT.encode())},
        )
        status, page = request(
            server, "POST", "/analyze", body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}",
                     "Content-Length": str(len(body))},
        )
        assert status == 200
        assert "2026-1-성인간호학-중간고사" in page
        assert list((tmp_path / "out").glob("2026-1-성인간호학-중간고사_*"))

    def test_summary_subject_not_double_prefixed(self, server, monkeypatch):
        # 문항 분석표에서 과목명을 자동 사용할 때 학년도 접두어를 중복으로 안 붙임
        openpyxl = pytest.importorskip("openpyxl")
        import io
        from tests.test_summary import school_rows

        wb = openpyxl.Workbook()
        ws = wb.active
        for row in school_rows():
            ws.append(row)
        buffer = io.BytesIO()
        wb.save(buffer)
        body = multipart_body(
            {"exam_id": "", "year": "2026", "semester": "1학기",
             "exam_type": "기말고사", "subject": ""},
            {"csv": ("표.xlsx", buffer.getvalue())},
        )
        status, page = request(
            server, "POST", "/analyze", body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}",
                     "Content-Length": str(len(body))},
        )
        assert status == 200
        assert "26-1 디지털리터러시와 AI활용(기말)" in page
        assert "2026-1 26-1" not in page

    def test_upload_page_has_api_key_field_with_local_storage(self, server):
        status, body = request(server, "GET", "/")
        assert status == 200
        assert 'name="api_key"' in body
        assert 'type="password"' in body
        assert "localStorage" in body           # 키는 브라우저에만 저장
        assert "itemclinic_api_key" in body

    def test_api_key_generates_improvements(self, server, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "itemclinic.server.generate_improvements",
            lambda prompt, model=None, api_key=None: "### 개선안: 문항 Q4 대체 문항",
        )
        body = multipart_body(
            {"exam_id": "키테스트", "exam_type": "중간고사", "subject": "",
             "skip_rows": "0", "api_key": "sk-ant-test"},
            {"csv": ("r.csv", CSV_CONTENT.encode())},
        )
        status, page = request(
            server, "POST", "/analyze", body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}",
                     "Content-Length": str(len(body))},
        )
        assert status == 200
        assert "Claude 개선안" in page
        assert "대체 문항" in page
        out_dirs = list((tmp_path / "out").glob("키테스트_*"))
        assert out_dirs and (out_dirs[0] / "improved_items.md").exists()
        assert "sk-ant-test" not in page        # 키가 응답에 노출되지 않음

    def test_api_error_still_returns_report(self, server, monkeypatch):
        def boom(prompt, model=None, api_key=None):
            raise RuntimeError("Claude API 호출에 실패했습니다: 401")
        monkeypatch.setattr("itemclinic.server.generate_improvements", boom)
        body = multipart_body(
            {"exam_id": "키오류", "exam_type": "중간고사", "subject": "",
             "skip_rows": "0", "api_key": "sk-ant-bad"},
            {"csv": ("r.csv", CSV_CONTENT.encode())},
        )
        status, page = request(
            server, "POST", "/analyze", body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}",
                     "Content-Length": str(len(body))},
        )
        assert status == 200                    # 분석 자체는 성공
        assert "자동 생성에 실패했습니다" in page
        assert "개선 프롬프트" in page          # 폴백 경로 안내 유지

    def test_analyze_returns_report(self, server, tmp_path):
        body = multipart_body(
            {"exam_id": "테스트시험", "exam_type": "중간고사", "subject": "",
             "skip_rows": "0"},
            {"csv": ("r.csv", CSV_CONTENT.encode())},
        )
        status, page = request(
            server, "POST", "/analyze", body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}",
                     "Content-Length": str(len(body))},
        )
        assert status == 200
        assert "문항분석 리포트" in page
        assert "Q4" in page  # 불량 문항 포함
        assert "개선 프롬프트" in page
        assert (tmp_path / "bank.json").exists()

    def test_bad_csv_shows_error_page(self, server):
        body = multipart_body(
            {"exam_id": "x", "exam_type": "일반", "subject": "", "skip_rows": "0"},
            {"csv": ("r.csv", b"garbage")},
        )
        status, page = request(
            server, "POST", "/analyze", body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}",
                     "Content-Length": str(len(body))},
        )
        assert status == 400
        assert "오류" in page

    def test_unknown_path_404(self, server):
        status, _ = request(server, "GET", "/etc/passwd")
        assert status == 404

    def test_xlsx_upload_with_skip_rows(self, server):
        openpyxl = pytest.importorskip("openpyxl")
        import io

        wb = openpyxl.Workbook()
        ws = wb.active
        for _ in range(7):
            ws.append(["시험 제목 영역"])
        for line in CSV_CONTENT.splitlines():
            ws.append(line.split(","))
        buffer = io.BytesIO()
        wb.save(buffer)

        body = multipart_body(
            {"exam_id": "엑셀시험", "exam_type": "기말고사", "subject": "",
             "skip_rows": "7"},
            {"csv": ("결과.xlsx", buffer.getvalue())},
        )
        status, page = request(
            server, "POST", "/analyze", body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}",
                     "Content-Length": str(len(body))},
        )
        assert status == 200
        assert "문항분석 리포트" in page
        assert "기말고사" in page

    def test_csv_with_title_rows_uses_default_skip(self, server):
        # skip_rows 필드를 안 보내도 기본 7행(제목 영역) 제외가 적용된다
        titled = "\n".join(["제목영역"] * 7) + "\n" + CSV_CONTENT
        body = multipart_body(
            {"exam_id": "제목있는CSV", "exam_type": "중간고사", "subject": ""},
            {"csv": ("r.csv", titled.encode())},
        )
        status, page = request(
            server, "POST", "/analyze", body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}",
                     "Content-Length": str(len(body))},
        )
        assert status == 200
        assert "문항분석 리포트" in page

    def test_school_summary_xlsx_auto_detected(self, server):
        # 학교 '문항 분석표' 형식은 자동 감지되어 상단 텍스트가 시험 정보로 쓰인다
        openpyxl = pytest.importorskip("openpyxl")
        import io
        from tests.test_summary import school_rows

        wb = openpyxl.Workbook()
        ws = wb.active
        for row in school_rows():
            ws.append(row)
        buffer = io.BytesIO()
        wb.save(buffer)

        body = multipart_body(
            {"exam_id": "", "exam_type": "기말고사", "subject": ""},
            {"csv": ("문항분석표.xlsx", buffer.getvalue())},
        )
        status, page = request(
            server, "POST", "/analyze", body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}",
                     "Content-Length": str(len(body))},
        )
        assert status == 200
        assert "문항 분석표(요약)" in page
        assert "디지털리터러시와 AI활용" in page   # 응시과목 텍스트 참조
        assert "229" in page                        # 응시인원 참조
        assert "개선 프롬프트" in page              # 불량 문항(2번) 존재

    def test_wrong_skip_rows_gives_clear_error(self, server):
        body = multipart_body(
            {"exam_id": "x", "exam_type": "일반", "skip_rows": "7"},
            {"csv": ("r.csv", CSV_CONTENT.encode())},
        )
        status, page = request(
            server, "POST", "/analyze", body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}",
                     "Content-Length": str(len(body))},
        )
        assert status == 400
        assert "오류" in page
