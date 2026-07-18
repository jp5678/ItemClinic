# ItemClinic 시스템 안내

개발·유지보수 관점의 구조 문서입니다. 사용법은 [USER_MANUAL.md](USER_MANUAL.md) 참고.

## 개요

- **목적**: 객관식 시험 문항분석(고전검사이론) 자동화 — 통계 산출, 불량문항 진단,
  개선 문항 생성, 문항은행 누적
- **스택**: Python 3.10+ 표준 라이브러리 (엑셀 읽기만 openpyxl, API 생성만 anthropic — 둘 다 선택)
- **실행 형태 3종**:
  1. **GitHub Pages 정적 웹** — https://jp5678.github.io/ItemClinic/ (루트 `index.html`
     단일 파일, 분석 엔진 JS 포팅, 브라우저 내 계산)
  2. 로컬 웹 서버 — `python3 -m itemclinic serve` (127.0.0.1 전용, `http.server` 기반)
  3. CLI — `python3 -m itemclinic analyze / bank-search`

<img src="qr-itemclinic.png" alt="배포 페이지 QR" width="150"> ← 배포 페이지 QR

> **이중 구현 주의**: 진단 규칙·프로파일·파서를 수정할 때는 Python(`itemclinic/`)과
> 정적 웹(`index.html`)을 **양쪽 모두** 고쳐야 한다. 문항은행은 Python 버전에만 있다.

## 데이터 흐름

```
업로드 파일 (CSV/XLSX)
   │  intake.load_any() ── 형식 자동 감지
   ├─ 학생별 응답 행렬 ──► loader ─► analyze ─► stats/icc/distractors ─► diagnose
   │                                                  │
   └─ 문항 분석표(요약) ──► summary.parse_summary() ──► diagnose(+답지반응률 규칙)
                                                       │
                    ┌──────────────────────────────────┤
                    ▼                  ▼               ▼
              report(.html)     serialize(.json)   improve(프롬프트/API)
                    │                                  │
                    └──────────► bank(item_bank.json) ◄┘
```

## 모듈 구성 (itemclinic/)

| 모듈 | 역할 |
|---|---|
| `loader.py` | CSV/엑셀 로딩, KEY 행 채점, skip_rows, 검증 |
| `excel.py` | .xlsx 읽기 (openpyxl), 숫자·날짜 정규화 |
| `intake.py` | 응답 행렬 vs 문항 분석표 자동 감지 |
| `stats.py` | 난이도 p, 수정 양류상관, 상하위 27% D, KR-20, 삭제 시 KR-20 |
| `icc.py` | 경험적 문항특성곡선 (총점 5분위 그룹) |
| `distractors.py` | 선택지별 전체/상위/하위 반응률 |
| `summary.py` | 학교 '문항 분석표' 파싱 + 메타데이터 + 답지반응률 진단 |
| `profiles.py` | 시험 유형별 판정 기준 (규준참조/준거참조) |
| `diagnose.py` | 플래그 규칙 엔진 (Severity: OK/WARNING/CRITICAL) |
| `analyze.py` | 응답 행렬 파이프라인 오케스트레이터 |
| `report.py` / `summary_report.py` | 한국어 HTML 리포트 (블루 팔레트, SVG ICC) |
| `svg.py` | ICC 꺾은선 SVG 렌더링 |
| `serialize.py` | diagnosis.json 직렬화 |
| `improve.py` | 개선 프롬프트 생성 + Claude API 호출 |
| `bank.py` | 문항은행(JSON) 누적·검색 |
| `multipart.py` | multipart/form-data 파서 (바이너리 안전) |
| `server.py` | HTTP 핸들러, 업로드 처리, API 키 1회성 사용 |
| `webui.py` | 업로드/오류 페이지 템플릿, 복사 버튼, localStorage 키 저장 |
| `cli.py` | analyze / bank-search / serve 서브커맨드 |

## 진단 규칙

기본(규준참조): 변별도 r<0 또는 <0.10 불량, <0.20 주의 · 난이도 p<0.20 또는
>0.90 주의 · 삭제 시 KR-20 상승 주의. 요약 형식 추가 규칙: 정답보다 선택률 높은
오답 불량, 선택률 5% 미만 오답지는 참고(등급 무영향).

유형별 조정(`profiles.py`): 진단평가는 낮은 p 허용, 형성평가는 높은 p 허용,
준거참조 둘 다 변별도 기준 완화(0.05/0.15) + KR-20 해석 문구 변경.
**음의 변별도는 모든 유형에서 불량.**

단위 처리 주의: 답지반응률·정답률은 열 단위로 %/비율을 판별한다
(`summary._normalize_scales` — 값 하나(예: 0.5)만으로는 0.5%인지 50%인지 알 수 없음).

## 보안·프라이버시

- 서버는 127.0.0.1 바인딩 — 외부 접속 불가. 업로드 한도 20MB.
- API 키: 요청 1회의 Claude 호출에만 사용, 서버·파일·로그에 저장하지 않음.
  브라우저 localStorage(`itemclinic_api_key`)에만 보관.
- 분석 결과(`web_analyses/`, `item_bank.json`)는 학생 응답이 포함되므로
  git에 커밋하지 않는다 (.gitignore 처리).

## 개발

```bash
python3 -m pytest tests/ --cov=itemclinic   # 85 tests, 커버리지 87%
python3 -m pyflakes itemclinic/ tests/      # 정적 검사
python3 examples/make_sample.py             # 데모 데이터 재생성
```

- 코딩 규약: 불변 데이터(frozen dataclass), 작은 모듈(<400줄), 한국어 사용자 메시지
- 새 입력 형식 추가 시: `intake.py`에 감지 규칙 + 전용 파서 모듈 추가
- 판정 기준 변경 시: `profiles.py`(유형별) 또는 `diagnose.py`(공통 규칙)만 수정
