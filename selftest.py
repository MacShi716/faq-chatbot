# -*- coding: utf-8 -*-
"""의존성 없이 돌아가는 자체 점검. 새로 클론한 뒤 가장 먼저 실행한다.

    python selftest.py
"""

import sys
from pathlib import Path

from normalize import detect_lang, normalize
from retriever import DEFAULT_FAQ_PATH, Retriever, load_faqs

FAILS = []


def check(name, cond, detail=""):
    if cond:
        print(f"  OK   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        FAILS.append(name)


print("[1] 정규화")
check("공백/문장부호 제거", normalize("휴학 신청은 언제 해요?") == "휴학신청은언제해요",
      normalize("휴학 신청은 언제 해요?"))
check("전각/반각 통일", normalize("ＡＢＣ") == "abc", normalize("ＡＢＣ"))

print("[2] 언어 감지")
check("한국어", detect_lang("휴학 신청은 언제 해요?") == "ko")
check("중국어", detect_lang("什么时候选课？") == "zh")
check("한자 섞인 한국어", detect_lang("수강신청 方法 알려줘") == "ko")

print("[3] 데이터 로드")
faqs = load_faqs(DEFAULT_FAQ_PATH)
check("FAQ 10건 이상", len(faqs) >= 10, f"{len(faqs)}건")
check("id 중복 없음", len({f.id for f in faqs}) == len(faqs))

print("[4] 검색 (difflib)")
index = Retriever(faqs, threshold=0.4, method="difflib")
m = index.answer("휴학 신청 기간이 언제인가요")
check("휴학 질문 매칭", m is not None and m.faq.id == "F01", getattr(m, "faq", None) and m.faq.id)
m = index.answer("怎么申请宿舍？", lang="zh")
check("중국어 기숙사 매칭", m is not None and m.faq.id == "F07", getattr(m, "faq", None) and m.faq.id)
check("무관한 질문은 미응답", index.answer("오늘 날씨 어때") is None)

print("[5] 검색 (tfidf, 선택 의존성)")
try:
    idx2 = Retriever(faqs, threshold=0.4, method="tfidf")
    m2 = idx2.answer("什么时候选课？", lang="zh")
    check("TF-IDF 동작", m2 is not None and m2.faq.id == "F04", getattr(m2, "faq", None) and m2.faq.id)
except ImportError:
    print("  SKIP scikit-learn 미설치 (1단계만 쓸 때는 문제 없음)")

print()
if FAILS:
    print(f"실패 {len(FAILS)}건: {FAILS}")
    sys.exit(1)
print("모두 통과")
