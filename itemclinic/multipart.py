"""multipart/form-data 최소 파서 (표준 라이브러리 cgi 모듈 폐지 대응).

바이너리 안전: 파일 내용을 그대로 bytes로 보존한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Optional


class MultipartError(ValueError):
    """업로드 형식 오류."""


@dataclass(frozen=True)
class Part:
    name: str
    filename: Optional[str]
    data: bytes

    @property
    def value(self) -> str:
        return self.data.decode("utf-8", errors="replace")


_BOUNDARY_RE = re.compile(r'boundary="?([^";]+)"?')
_NAME_RE = re.compile(r'name="([^"]*)"')
_FILENAME_RE = re.compile(r'filename="([^"]*)"')


def parse_multipart(body: bytes, content_type: str) -> Dict[str, Part]:
    """요청 본문을 {필드명: Part}로 파싱한다."""
    if "multipart/form-data" not in (content_type or ""):
        raise MultipartError("multipart/form-data 요청이 아닙니다.")
    match = _BOUNDARY_RE.search(content_type)
    if not match:
        raise MultipartError("업로드 경계(boundary)를 찾을 수 없습니다.")
    delimiter = b"--" + match.group(1).encode()

    parts: Dict[str, Part] = {}
    for segment in body.split(delimiter):
        part = _parse_segment(segment)
        if part is not None:
            parts[part.name] = part
    if not parts:
        raise MultipartError("업로드된 데이터가 비어 있습니다.")
    return parts


def _parse_segment(segment: bytes) -> Optional[Part]:
    # 전문(preamble)·종결 마커("--")·빈 조각은 건너뛴다
    if segment.startswith(b"\r\n"):
        segment = segment[2:]
    if not segment or segment.startswith(b"--"):
        return None
    if b"\r\n\r\n" not in segment:
        return None
    header_blob, data = segment.split(b"\r\n\r\n", 1)
    # 데이터 뒤에는 다음 경계 직전의 CRLF 정확히 하나가 붙는다
    if data.endswith(b"\r\n"):
        data = data[:-2]
    headers = header_blob.decode("utf-8", errors="replace")
    disposition = next(
        (line for line in headers.split("\r\n")
         if line.lower().startswith("content-disposition:")),
        None,
    )
    if disposition is None:
        return None
    name_match = _NAME_RE.search(disposition)
    if not name_match:
        return None
    file_match = _FILENAME_RE.search(disposition)
    return Part(
        name=name_match.group(1),
        filename=file_match.group(1) if file_match else None,
        data=data,
    )
