"""multipart/form-data 파서 테스트."""
import pytest

from itemclinic.multipart import parse_multipart, MultipartError

BOUNDARY = "----WebKitFormBoundaryX"
CT = f"multipart/form-data; boundary={BOUNDARY}"


def build_body(parts):
    chunks = []
    for name, filename, data in parts:
        disp = f'form-data; name="{name}"'
        if filename is not None:
            disp += f'; filename="{filename}"'
        chunks.append(
            f"--{BOUNDARY}\r\nContent-Disposition: {disp}\r\n\r\n".encode()
            + data + b"\r\n"
        )
    chunks.append(f"--{BOUNDARY}--\r\n".encode())
    return b"".join(chunks)


class TestParseMultipart:
    def test_field_and_file(self):
        body = build_body([
            ("exam_id", None, "중간고사".encode()),
            ("csv", "r.csv", b"student,Q1\nKEY,A\ns1,A\n"),
        ])
        parts = parse_multipart(body, CT)
        assert parts["exam_id"].value == "중간고사"
        assert parts["csv"].filename == "r.csv"
        assert b"KEY,A" in parts["csv"].data

    def test_binary_content_preserved(self):
        payload = bytes(range(256))
        body = build_body([("f", "bin.dat", payload)])
        parts = parse_multipart(body, CT)
        assert parts["f"].data == payload

    def test_missing_boundary_raises(self):
        with pytest.raises(MultipartError):
            parse_multipart(b"data", "multipart/form-data")

    def test_wrong_content_type_raises(self):
        with pytest.raises(MultipartError):
            parse_multipart(b"data", "application/json")
