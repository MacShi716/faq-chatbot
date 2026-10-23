# -*- coding: utf-8 -*-
"""faq.csv 품질 점검.

두 단계로 나눠서 본다.
  ERROR : 파일이 깨졌거나 검색이 불가능한 문제 (중복 id, 질문 없음, 컬럼 누락)
  WARN  : 아직 데이터가 준비되지 않은 상태 (플레이스홀더 답변, 출처/확인일 없음, 태그 부족)

    python validate_data.py            # ERROR 만 실패 처리
    python validate_data.py --strict   # WARN 도 실패 처리 (데이터 완성 후 사용)
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

from retriever import DEFAULT_FAQ_PATH, REQUIRED_COLUMNS, is_filled, split_variants

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MIN_TAGS = 5
MIN_KO_VARIANTS = 3


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--faq", type=Path, default=DEFAULT_FAQ_PATH)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    with args.faq.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        header = reader.fieldnames or []

    errors: list[str] = []
    warns: list[str] = []
    missing = REQUIRED_COLUMNS - set(header)
    if missing:
        errors.append(f"필수 컬럼 누락: {sorted(missing)}")

    ids = Counter((r.get("id") or "").strip() for r in rows)
    for faq_id, n in ids.items():
        if not faq_id:
            errors.append("id 가 비어 있는 행이 있습니다.")
        elif n > 1:
            errors.append(f"id 중복: {faq_id} ({n}회)")

    placeholder_ko = placeholder_zh = 0
    for i, row in enumerate(rows, start=2):
        faq_id = (row.get("id") or "").strip() or f"{i}행"

        if not (row.get("question_ko") or "").strip() and not (row.get("question_zh") or "").strip():
            errors.append(f"{faq_id}: 질문이 전부 비어 있습니다.")

        if not is_filled(row.get("answer")):
            placeholder_ko += 1
        if not is_filled(row.get("answer_zh")):
            placeholder_zh += 1

        if not (row.get("source") or "").strip():
            warns.append(f"{faq_id}: source 없음")
        checked = (row.get("checked_at") or "").strip()
        if not checked:
            warns.append(f"{faq_id}: checked_at 없음")
        elif not DATE_RE.match(checked):
            errors.append(f"{faq_id}: checked_at 형식 오류 ({checked}) — YYYY-MM-DD")

        tags = split_variants(row.get("tags"))
        if len(tags) < MIN_TAGS:
            warns.append(f"{faq_id}: 태그 {len(tags)}개 (권장 {MIN_TAGS}개 이상)")
        ko_variants = split_variants(row.get("question_ko"))
        if len(ko_variants) < MIN_KO_VARIANTS:
            warns.append(f"{faq_id}: 한국어 표현 {len(ko_variants)}개 (권장 {MIN_KO_VARIANTS}개 이상)")

        if any(tag.strip() in ("어디", "언제", "어떻게", "怎么办", "在哪") for tag in tags):
            warns.append(f"{faq_id}: 범용어 태그는 오탐을 만든다 ({tags})")

    print(f"파일: {args.faq}")
    print(f"행 수: {len(rows)}  |  ERROR {len(errors)}  |  WARN {len(warns)}")
    print(f"답변 미작성: 한국어 {placeholder_ko}/{len(rows)}, 중국어 {placeholder_zh}/{len(rows)}")

    if errors:
        print("\n[ERROR]")
        for e in errors:
            print("  -", e)
    if warns:
        print("\n[WARN] (데이터 준비 중이면 정상)")
        for w in warns[:40]:
            print("  -", w)
        if len(warns) > 40:
            print(f"  ... 외 {len(warns) - 40}건")

    if errors or (args.strict and warns):
        print("\n실패")
        return 1
    print("\n통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
