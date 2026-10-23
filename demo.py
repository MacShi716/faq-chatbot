# -*- coding: utf-8 -*-
"""터미널에서 바로 보는 데모. Streamlit 없이 검색 품질만 확인한다.

    python demo.py            # 기본 8문항
    python demo.py --method tfidf
"""

import argparse

from retriever import DEFAULT_FAQ_PATH, DEFAULT_THRESHOLD, Retriever, load_faqs

SAMPLE = [
    "휴학 신청은 언제 해요?",
    "졸업하려면 학점 몇 개 들어야 해요?",
    "수강신청 날짜 알려주세요",
    "기숙사 들어가려면 어떻게 해요",
    "성적 조회는 어디서 해요",
    "什么时候选课？",
    "宿舍费用多少",
    "食堂在哪里？",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=["difflib", "tfidf"], default="difflib")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args()

    index = Retriever(faqs=load_faqs(DEFAULT_FAQ_PATH), threshold=args.threshold, method=args.method)
    print(f"방식: {args.method} | 임계값: {args.threshold} | FAQ {len(index.faqs)}건\n")
    print("=" * 78)

    for q in SAMPLE:
        top = index.search(q, top_k=2)
        hit = index.answer(q)
        print(f"\n[질문] {q}")
        if hit:
            print(f"  → {hit.faq.id} (유사도 {hit.score:.2f})")
            print(f"    {hit.faq.answer[:70]}")
            print(f"    출처: {hit.faq.source or '-'} / 확인일: {hit.faq.checked_at or '-'}")
        else:
            best = f" (최고 후보 {top[0].score:.2f} < {args.threshold})" if top else ""
            print(f"  → 답변 없음 · 학과 사무실 문의 안내{best}")
        if top:
            print("    후보: " + ", ".join(f"{m.faq.id}({m.score:.2f})" for m in top))

    print("\n" + "=" * 78)
    print("실행 화면: streamlit run app.py")


if __name__ == "__main__":
    main()
