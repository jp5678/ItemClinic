"""ICC 곡선 인라인 SVG 렌더링 (외부 라이브러리 없이)."""
from __future__ import annotations

from typing import Sequence

from .models import ICCGroup

W, H = 320, 200
PAD_L, PAD_R, PAD_T, PAD_B = 40, 12, 14, 32


def icc_svg(curve: Sequence[ICCGroup], color: str = "#2563eb") -> str:
    """능력그룹(x) 대 정답률(y) 꺾은선 SVG를 반환한다."""
    n = len(curve)
    if n == 0:
        return ""
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B

    def x(i: int) -> float:
        return PAD_L + (plot_w * i / max(1, n - 1))

    def y(p: float) -> float:
        return PAD_T + plot_h * (1 - p)

    points = " ".join(f"{x(i):.1f},{y(g.proportion_correct):.1f}" for i, g in enumerate(curve))
    dots = "".join(
        f'<circle cx="{x(i):.1f}" cy="{y(g.proportion_correct):.1f}" r="3.5" fill="{color}">'
        f"<title>그룹 {i + 1} (n={g.n}, 평균총점 {g.mean_total:.1f}): "
        f"정답률 {g.proportion_correct:.0%}</title></circle>"
        for i, g in enumerate(curve)
    )
    gridlines = "".join(
        f'<line x1="{PAD_L}" y1="{y(v):.1f}" x2="{W - PAD_R}" y2="{y(v):.1f}" '
        f'stroke="#e5e7eb" stroke-width="1"/>'
        f'<text x="{PAD_L - 6}" y="{y(v) + 4:.1f}" text-anchor="end" '
        f'font-size="10" fill="#6b7280">{v:.1f}</text>'
        for v in (0.0, 0.25, 0.5, 0.75, 1.0)
    )
    xlabels = "".join(
        f'<text x="{x(i):.1f}" y="{H - PAD_B + 16}" text-anchor="middle" '
        f'font-size="10" fill="#6b7280">G{i + 1}</text>'
        for i in range(n)
    )
    return (
        f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="문항특성곡선">'
        f"{gridlines}"
        f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.5"/>'
        f"{dots}{xlabels}"
        f'<text x="{(PAD_L + W - PAD_R) / 2}" y="{H - 4}" text-anchor="middle" '
        f'font-size="10" fill="#6b7280">능력 그룹 (하위 → 상위)</text>'
        "</svg>"
    )
