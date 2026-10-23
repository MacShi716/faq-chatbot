# -*- coding: utf-8 -*-
"""임계값 민감도 실험.

같은 평가셋으로 임계값만 바꿔가며 정확도와 미응답 비율을 비교한다.
"왜 0.4 인가"를 설명할 근거 자료로 쓴다.

    python tune.py
"""

from datetime import datetime
from pathlib import Path

from evaluate import DEFAULT_EVAL_PATH, run
from retriever import DEFAULT_FAQ_PATH

THRESHOLDS = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]
METHODS = ["difflib", "tfidf"]


def sweep(method: str) -> list[dict]:
    rows = []
    for th in THRESHOLDS:
        report = run(method, th, DEFAULT_FAQ_PATH, DEFAULT_EVAL_PATH)
        answered = sum(1 for r in report["results"] if r["predicted"])
        rows.append({
            "threshold": th,
            "overall": report["accuracy"],
            "ko": report["by_lang"]["ko"]["accuracy"],
            "zh": report["by_lang"]["zh"]["accuracy"],
            "answered": answered,
            "total": report["total"],
        })
    return rows


def main() -> None:
    lines = [
        "# 임계값 민감도",
        "",
        f"- 실행: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- 평가셋: {DEFAULT_EVAL_PATH.name} (50문항)",
        "- ⚠️ 평가셋을 만든 사람과 태그를 만든 사람이 같아 수치가 낙관적이다.",
        "",
    ]
    for method in METHODS:
        rows = sweep(method)
        print(f"\n[{method}]")
        print("임계값 | 전체 | 한국어 | 중국어 | 응답률")
        print("------|------|--------|--------|-------")
        lines += [f"## {method}", "", "| 임계값 | 전체 | 한국어 | 중국어 | 응답률 |", "|---|---|---|---|---|"]
        best = max(rows, key=lambda r: r["overall"])
        for r in rows:
            mark = " ←" if r is best else ""
            print(f"{r['threshold']:.2f}  | {r['overall']:5.1f}% | {r['ko']:5.1f}% | {r['zh']:5.1f}% | "
                  f"{r['answered']}/{r['total']}{mark}")
            lines.append(f"| {r['threshold']:.2f} | {r['overall']:.1f}% | {r['ko']:.1f}% | {r['zh']:.1f}% | "
                         f"{r['answered']}/{r['total']} |")
        lines += ["", f"최고: 임계값 {best['threshold']:.2f} → {best['overall']:.1f}%", ""]

    out = Path(__file__).parent / "reports"
    out.mkdir(exist_ok=True)
    path = out / f"threshold-sweep-{datetime.now():%Y%m%d-%H%M%S}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n보고서: {path}")


if __name__ == "__main__":
    main()
