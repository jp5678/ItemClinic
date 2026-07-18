"""데모용 시뮬레이션 응답 생성.

N=236, 25문항 5지선다. 실제 중간고사 분석 상황을 재현:
- Q5: 상위권일수록 매력적 오답 B를 고르는 음의 변별도 문항
- Q12: 정답률 95%의 너무 쉬운 문항
- Q20: 정답률 12%의 너무 어려운 문항
- 나머지: 변별도가 낮은~중간 수준으로 KR-20이 0.65 근처가 되도록 설정
"""
import csv
import math
import random
from pathlib import Path

N_STUDENTS = 236
N_ITEMS = 25
OPTIONS = ["A", "B", "C", "D", "E"]
SEED = 20260718


def logistic(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def make_items(rng: random.Random):
    items = []
    for j in range(N_ITEMS):
        item_id = f"Q{j + 1}"
        a = rng.uniform(0.5, 1.1)   # 낮은 변별 → KR-20 0.6대
        b = rng.uniform(-1.2, 1.2)
        key = rng.choice(OPTIONS)
        trap = None
        if item_id == "Q5":
            a, b = -0.5, 0.0        # 음의 변별
            trap = "B" if key != "B" else "C"
        elif item_id == "Q12":
            a, b = 0.8, -3.2        # 너무 쉬움
        elif item_id == "Q20":
            a, b = 0.7, 2.6         # 너무 어려움
        items.append({"id": item_id, "a": a, "b": b, "key": key, "trap": trap})
    return items


def simulate(rng: random.Random, items):
    rows = []
    for i in range(N_STUDENTS):
        theta = rng.gauss(0, 1)
        row = [f"S{i + 1:03d}"]
        for it in items:
            p = 0.18 + 0.82 * logistic(it["a"] * (theta - it["b"]))  # 추측 반영
            if rng.random() < p:
                row.append(it["key"])
            else:
                distractors = [o for o in OPTIONS if o != it["key"]]
                if it["trap"] and rng.random() < 0.6:
                    row.append(it["trap"])
                else:
                    row.append(rng.choice(distractors))
        rows.append(row)
    return rows


# 학교 시스템 출력물과 동일하게 상단 7행은 제목 영역 (분석 시 --skip-rows 7)
TITLE_ROWS = [
    ["2026학년도 1학기 성인간호학"],
    [],
    ["중간고사 응답 결과"],
    ["출력일: 2026-07-18"],
    [],
    ["청암대학교 간호학과"],
    ["※ 아래는 학생별 응답 데이터"],
]


def main():
    rng = random.Random(SEED)
    items = make_items(rng)
    rows = simulate(rng, items)
    out = Path(__file__).parent / "midterm_sample.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(TITLE_ROWS)
        writer.writerow(["student"] + [it["id"] for it in items])
        writer.writerow(["KEY"] + [it["key"] for it in items])
        writer.writerows(rows)
    print(f"생성: {out} (제목 7행 + N={N_STUDENTS}, {N_ITEMS}문항, --skip-rows 7로 분석)")


if __name__ == "__main__":
    main()
