# -*- coding: utf-8 -*-
"""의존성 없이 돌아가는 자체 점검. 새로 클론한 뒤 가장 먼저 실행한다.

    python selftest.py
"""

import sys
from pathlib import Path

from normalize import detect_lang, normalize
from retriever import DEFAULT_FAQ_PATH, Faq, Retriever, is_filled, load_faqs

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

print("[6] 답변 언어 (answer_zh 우선, 없으면 한국어 폴백)")
check("빈 답변은 미작성", not is_filled(""))
check("[작성 필요] 는 미작성", not is_filled("[작성 필요] 확인 후 기입"))
check("채운 답변은 작성됨", is_filled("휴학 신청은 3월과 9월에 가능합니다."))

filled = Faq("T01", "질문", "问题", "한국어 답변", "출처", "2026-10-25", answer_zh="中文答案")
check("중국어 답변 우선", filled.answer_for("zh") == ("中文答案", False), filled.answer_for("zh"))
check("한국어 화면은 한국어", filled.answer_for("ko") == ("한국어 답변", False), filled.answer_for("ko"))

empty = Faq("T02", "질문", "问题", "한국어 답변", "출처", "2026-10-25", answer_zh="[작성 필요]")
check("중국어 미작성이면 폴백", empty.answer_for("zh") == ("한국어 답변", True), empty.answer_for("zh"))

print("[7] faq.csv 에 answer_zh 컬럼 존재")
check("12행 모두 answer_zh 로드", all(hasattr(f, "answer_zh") for f in faqs))
check("현재는 전부 미작성(폴백 상태)", all(f.answer_for("zh")[1] for f in faqs))

print("[8] 키워드 태그로 중국어 질문 연결")
check("전 행에 태그 존재", all(f.tag_list() for f in faqs))
m = index.answer("第一工学馆在哪")
check("건물 질문 → F13", m is not None and m.faq.id == "F13", getattr(m, "faq", None) and m.faq.id)
m = index.answer("工学馆的位置")
check("다른 표현도 F13", m is not None and m.faq.id == "F13", getattr(m, "faq", None) and m.faq.id)
m = index.answer("签证快到期了怎么办")
check("태그 보정(F09)", m is not None and m.faq.id == "F09", getattr(m, "faq", None) and m.faq.id)
check("무관한 질문은 여전히 미응답", index.answer("今天天气怎么样") is None)
m = index.answer("系办公室在哪里", lang="zh")
check("사무실 질문은 F10 유지", m is not None and m.faq.id == "F10", getattr(m, "faq", None) and m.faq.id)

print()
if FAILS:
    print(f"실패 {len(FAILS)}건: {FAILS}")
    sys.exit(1)
print("모두 통과")
