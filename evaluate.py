# -*- coding: utf-8 -*-
"""평가 스크립트: 50문항(한국어 25 / 중국어 25)으로 정확도를 측정한다.

사용법:
    python evaluate.py --method difflib --out reports
    python evaluate.py --method tfidf   --out reports

정확도 정의(계획서와 동일):
    상위 1건 매칭 FAQ 의 id 가 expected_id 와 같으면 정답.
    임계값 미달로 답변하지 않은 경우도 오답으로 계산한다.

'화면 기준' 정확도도 함께 낸다: 화면(chat_logic.pick_match)과 같은 판단으로 약한 매칭 가드·미작성 초안을 적용해
실제로 답으로 보여주는 FAQ 가 expected_id 와 같으면 정답. 답 없음(학과 사무실 문의 안내)은 오답으로 센다.
주의: 질문 작성자와 정답 작성자가 같은 내부 평가셋이라 점수가 실제보다 좋게 나올 수 있다.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

from chat_logic import pick_match
from normalize import detect_lang
from retriever import DEFAULT_FAQ_PATH, DEFAULT_THRESHOLD, Retriever, load_faqs

DEFAULT_EVAL_PATH = Path(__file__).parent / "data" / "eval.csv"


def load_eval(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for i, row in enumerate(rows, start=2):
        for key in ("qid", "lang", "question", "expected_id"):
            if not (row.get(key) or "").strip():
                raise ValueError(f"eval.csv {i}행: '{key}' 가 비어 있습니다.")
    return rows


def run(method: str, threshold: float, faq_path: Path, eval_path: Path) -> dict:
    index = Retriever(faqs=load_faqs(faq_path), threshold=threshold, method=method)
    rows = load_eval(eval_path)

    results = []
    for row in rows:
        question = row["question"].strip()
        lang = (row["lang"] or detect_lang(question)).strip()
        expected = row["expected_id"].strip()
        candidates = index.search(question, lang=lang, top_k=1)
        hit = bool(candidates) and candidates[0].score >= threshold
        predicted = candidates[0].faq.id if hit else ""
        score = candidates[0].score if candidates else 0.0
        shown = pick_match(question, candidates, lang, threshold)  # 화면에 실제로 답으로 나오는 FAQ
        app_predicted = shown.faq.id if shown else ""
        results.append({
            "qid": row["qid"], "lang": lang, "question": question,
            "expected": expected, "predicted": predicted,
            "score": score, "correct": predicted == expected,
            "app_predicted": app_predicted, "app_correct": app_predicted == expected,
        })

    total = len(results)
    correct = sum(r["correct"] for r in results)
    app_correct = sum(r["app_correct"] for r in results)
    by_lang = {}
    for lang in ("ko", "zh"):
        subset = [r for r in results if r["lang"] == lang]
        by_lang[lang] = {
            "total": len(subset),
            "correct": sum(r["correct"] for r in subset),
            "accuracy": (sum(r["correct"] for r in subset) / len(subset) * 100) if subset else 0.0,
        }

    return {
        "method": method, "threshold": threshold, "total": total, "correct": correct,
        "accuracy": correct / total * 100 if total else 0.0,
        "by_lang": by_lang, "results": results,
        "app_correct": app_correct, "app_accuracy": app_correct / total * 100 if total else 0.0,
    }


def write_report(report: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"eval-{report['method']}-{stamp}.md"

    lines = [
        f"# 평가 결과 · {report['method']}",
        "",
        f"- 실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- 임계값: {report['threshold']}",
        f"- 전체 정확도: **{report['correct']}/{report['total']} = {report['accuracy']:.1f}%**",
        f"- 화면 기준(약한 매칭 가드·미작성 초안 제외): **{report['app_correct']}/{report['total']} = {report['app_accuracy']:.1f}%**",
        "- 내부 평가셋(질문 작성자 = 정답 작성자)이라 실제 사용자 질문보다 점수가 좋게 나올 수 있다.",
        "",
        "## 언어별",
        "",
        "| 언어 | 정답 | 전체 | 정확도 |",
        "|---|---|---|---|",
    ]
    for lang, label in (("ko", "한국어"), ("zh", "중국어")):
        s = report["by_lang"][lang]
        lines.append(f"| {label} | {s['correct']} | {s['total']} | {s['accuracy']:.1f}% |")

    failures = [r for r in report["results"] if not r["correct"]]
    lines += ["", f"## 오답 {len(failures)}건", ""]
    if failures:
        lines += ["| 문항 | 질문 | 기대 | 예측 | 유사도 |", "|---|---|---|---|---|"]
        for r in failures:
            q = r["question"].replace("|", "\\|")
            lines.append(f"| {r['qid']} | {q} | {r['expected']} | {r['predicted'] or '(미응답)'} | {r['score']:.3f} |")
    else:
        lines.append("없음")

    changed = [r for r in report["results"] if r["app_predicted"] != r["predicted"]]
    lines += ["", f"## 화면 기준에서 달라진 문항 {len(changed)}건", ""]
    if changed:
        lines += ["| 문항 | 질문 | 기대 | 검색 1위 | 화면 | 유사도 |", "|---|---|---|---|---|---|"]
        for r in changed:
            q = r["question"].replace("|", "\\|")
            lines.append(f"| {r['qid']} | {q} | {r['expected']} | {r['predicted'] or '(미응답)'} | "
                         f"{r['app_predicted'] or '(답 없음)'} | {r['score']:.3f} |")
    else:
        lines.append("없음")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=["difflib", "tfidf"], default="difflib")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--faq", type=Path, default=DEFAULT_FAQ_PATH)
    parser.add_argument("--eval", type=Path, default=DEFAULT_EVAL_PATH)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "reports")
    args = parser.parse_args()

    report = run(args.method, args.threshold, args.faq, args.eval)
    path = write_report(report, args.out)

    print(f"방식={report['method']} 임계값={report['threshold']}")
    print(f"전체 {report['correct']}/{report['total']} = {report['accuracy']:.1f}%")
    for lang, label in (("ko", "한국어"), ("zh", "중국어")):
        s = report["by_lang"][lang]
        print(f"  {label}: {s['correct']}/{s['total']} = {s['accuracy']:.1f}%")
    print(f"화면 기준(약한 매칭 가드·미작성 초안 제외) {report['app_correct']}/{report['total']} = {report['app_accuracy']:.1f}%")
    print(f"보고서: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
