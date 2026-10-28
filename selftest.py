# -*- coding: utf-8 -*-
"""의존성 없이 돌아가는 자체 점검. 새로 클론한 뒤 가장 먼저 실행한다.

    python selftest.py
"""

import re
import sys
from pathlib import Path

from chat_logic import detect_intent
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

empty = Faq("T02", "질문", "问题", "한국어 답변", "출처", "2026-10-25", answer_zh="")
check("중국어 답변이 비어 있으면 한국어 폴백", empty.answer_for("zh") == ("한국어 답변", True), empty.answer_for("zh"))
draft = Faq("T03", "질문", "问题", "한국어 답변", "출처", "2026-10-25", answer_zh="[待填写] 中文草稿")
check("중국어 초안은 미확인이어도 중국어로 표시", draft.answer_for("zh") == ("[待填写] 中文草稿", False), draft.answer_for("zh"))

print("[7] faq.csv 에 answer_zh 컬럼 존재")
check(f"{len(faqs)}행 모두 answer_zh 로드", all(hasattr(f, "answer_zh") for f in faqs))
check("현재는 전부 중국어 초안(미확인) 표시", all(f.answer_for("zh")[0] == f.answer_zh.strip() and not f.answer_for("zh")[1] for f in faqs))

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

print("[9] 비정상 입력 (예외 없이 처리되는지)")
edge_cases = {
    "빈 문자열": "",
    "공백만": "     ",
    "문장부호만": "???!!!...",
    "아주 긴 입력": "휴학 " * 500,
    "영문만": "hello world",
    "이모지": "😀😀😀",
    "숫자만": "1234567890",
    "한중 혼합": "휴학 어떻게 申请",
}
for name, value in edge_cases.items():
    try:
        r = index.search(value)
        ok = isinstance(r, list)
        index.answer(value)
    except Exception as exc:  # noqa: BLE001 - 어떤 예외든 잡아서 실패로 기록
        ok = False
        detail = f"{type(exc).__name__}: {exc}"
    else:
        detail = ""
    check(name, ok, detail)

check("None 정규화", normalize(None) == "")
check("탭/줄바꿈 제거", normalize("휴학\n신청\t기간") == "휴학신청기간")

print("[10] 대화 의도(인사·후속)")
check("인사 ko", detect_intent("안녕하세요!") == "greet")
check("인사 zh", detect_intent("你好") == "greet")
check("감사", detect_intent("고마워요~") == "thanks" and detect_intent("谢谢") == "thanks")
check("후속 요청", detect_intent("더 자세히") == "followup" and detect_intent("再详细点") == "followup")
check("언어 전환 요청", detect_intent("중국어로") == "to_zh" and detect_intent("用韩语") == "to_ko")
check("실제 질문은 가로채지 않음", detect_intent("다시 학교 다니려면") is None)
check("실제 질문(휴학)", detect_intent("휴학 신청은 언제 해요?") is None)
check("실제 질문(중국어)", detect_intent("什么时候选课？") is None)

print("[11] 캠퍼스맵 장소 FAQ (F13 + F42 이후, 지도 번호 1~44)")
MAP_URL = "https://inews.kyungnam.ac.kr/bbs/view.html?idxno=39517"
map_rows = [f for f in faqs if MAP_URL in f.source and "경남대 캠퍼스맵" in f.answer]  # 지도 위치 행(F13, F42~F84)
by_no = {}
for f in map_rows:
    mm = re.search(r"경남대 캠퍼스맵 (\d+)번", f.answer)
    if mm:
        by_no.setdefault(int(mm.group(1)), []).append(f)
missing_no = sorted(set(range(1, 45)) - set(by_no))
check("지도 번호 1~44 빠짐없이 있음", not missing_no and set(by_no) == set(range(1, 45)), missing_no)
check("번호마다 FAQ 정확히 한 행", len(map_rows) == 44 and all(len(v) == 1 for v in by_no.values()), len(map_rows))
check("11번은 F13(제1공학관)", 11 in by_no and by_no[11][0].id == "F13")
check("지도 행 전부 답변(한/중) 작성됨", all(is_filled(f.answer) and is_filled(f.answer_zh) for f in map_rows))
check("지도 행 전부 답변에 링크 포함(한/중)", all(MAP_URL in f.answer and MAP_URL in f.answer_zh for f in map_rows))
# F46/F69 는 중문 명칭이 추정이라 '待确认'(checked_at 비움). 나머지 지도 행은 '已确认'(2026-10-28).
UNCONFIRMED_MAP = {"F46", "F69"}
check("지도 행 전부 출처(캠퍼스맵) 있음", all("캠퍼스맵" in f.source for f in map_rows))
check("지도 행 확인일: 확인된 행은 2026-10-28, F46/F69(待确认)는 비어 있음",
      all((f.checked_at == "") if f.id in UNCONFIRMED_MAP else (f.checked_at == "2026-10-28") for f in map_rows))
check("F46/F69 외 지도 행 42개가 확인됨(已确认)",
      sum(1 for f in map_rows if f.id not in UNCONFIRMED_MAP and f.checked_at == "2026-10-28") == 42)
check("중국어 답변의 지도 번호가 한국어와 같음",
      all(f"地图 {no} 号" in v[0].answer_zh for no, v in by_no.items()))
check("층·호실은 지어내지 않고 안내 문구만 있음",
      all("층·호실" in f.answer and "房间号" in f.answer_zh for f in map_rows))
check("FAQ id 중복 없음(F42 이후 포함)", len({f.id for f in faqs}) == len(faqs))

place_cases = [
    ("법정관", 23), ("法政馆", 23), ("体育馆", 30), ("제1공학관 어디예요", 11), ("第二工学馆在哪", 13),
    ("성훈관 어디예요", 15), ("제3공학관 위치", 15), ("제1한마생활관", 31), ("10.18광장 어디예요", 6),
    ("정문게시판 어디예요", 2), ("正门布告栏在哪", 2), ("정문 어디예요", 1), ("서문 IC 어디예요", 28),
    ("中央图书馆怎么走", 22), ("도서관 어디예요", 22), ("图书馆在哪", 22), ("조소실B 어디예요", 39),
    ("汉马馆在哪", 26), ("한마관", 26), ("孤云馆", 10), ("成训馆", 15), ("第三工学馆在哪", 15),
    ("제2한마관 어디예요", 32), ("第三汉马馆", 33), ("第一宿舍楼在哪", 31),
    ("操场在哪", 37), ("运动场在哪", 37), ("大运动场在哪", 9), ("大操场在哪", 9),
]
for q, no in place_cases:
    m = index.answer(q)
    want = by_no[no][0].id if no in by_no else None
    check(f"장소 질문 '{q}' → 지도 {no}번", m is not None and m.faq.id == want, getattr(m, "faq", None) and m.faq.id)
check("한마관(26)은 중국어 답변에 食堂 표기, 31~33은 宿舍 표기",
      "食堂" in by_no[26][0].answer_zh and all("宿舍" in by_no[n][0].answer_zh for n in (31, 32, 33)))
check("공식 중국어 이름 반영(10 孤云馆 / 15 成训馆 / 37 运动场)",
      "孤云馆" in by_no[10][0].answer_zh and "成训馆" in by_no[15][0].answer_zh and "运动场" in by_no[37][0].answer_zh)
by_id = {f.id: f for f in faqs}
check("F85·F86(팀 확인 정보) 존재: 링크·전화·확인일·출처",
      all(i in by_id and MAP_URL in by_id[i].answer and MAP_URL in by_id[i].answer_zh and by_id[i].checked_at == "2026-10-28"
          and "팀 확인 정보" in by_id[i].source for i in ("F85", "F86")))
check("F85 설계관 7층·전화", "디자인관(캠퍼스맵 36번) 7층" in by_id["F85"].answer and "055-249-2914" in by_id["F85"].answer_zh)
check("F86 창조관 1층·전화", "창조관(캠퍼스맵 43번) 1층" in by_id["F86"].answer and "055-249-2299" in by_id["F86"].answer_zh)
for q, fid in [("留学生服务中心在哪", "F85"), ("유학생서비스센터 어디", "F85"), ("国际处在哪", "F86"), ("국제처 어디예요", "F86"),
               ("设计馆在哪", by_no[36][0].id), ("디자인관 어디예요", by_no[36][0].id), ("创造馆在哪", by_no[43][0].id), ("창조관", by_no[43][0].id)]:
    m = index.answer(q)
    check(f"'{q}' → {fid}", m is not None and m.faq.id == fid, getattr(m, "faq", None) and m.faq.id)
check("지도와 무관한 질문은 여전히 미응답", index.answer("오늘 날씨 어때") is None and index.answer("今天天气怎么样") is None)

print("[12] Tier B (FAQ 에 없는 질문 → AI 자율 답변). HTTP 는 전부 가짜로 바꿔 끼운다. 실제 호출 없음")
import ast
import json
import tempfile

import llm_answer as la
from chat_logic import build_entry as _build_entry
from i18n import STRINGS


def build_entry(*args, ai_enabled=True, **kwargs):
    """[12] 의 기존 점검은 '사용자가 AI 대화를 켠 상태'를 가정한다. 토글 꺼짐 점검은 ai_enabled=False 를 명시한다."""
    return _build_entry(*args, ai_enabled=ai_enabled, **kwargs)

_saved = (la._get, la._http_post, la._now, la.LOG_PATH)
_tmp = Path(tempfile.mkdtemp(prefix="tierb_selftest_"))
CFG, CALLS, CLOCK = {}, [], [1000.0]
TOKEN, GKEY = "SECRET-CF-TOKEN-ABC", "SECRET-GROQ-KEY-XYZ"
CF_ONLY = {"LLM_ENABLED": "on", "CLOUDFLARE_ACCOUNT_ID": "acc123", "CLOUDFLARE_API_TOKEN": TOKEN}
BOTH = {**CF_ONLY, "GROQ_API_KEY": GKEY}


def cf_ok(text="클라우드플레어 답변이에요", neurons=12.5):
    return {"result": {"choices": [{"message": {"content": text}}], "usage": {"neurons": neurons}}, "success": True}


def groq_ok(text="groq 답변이에요"):
    return {"choices": [{"message": {"content": text}}], "usage": {"total_tokens": 30}}


def setup(cfg, handler):
    """설정과 가짜 HTTP 를 설치하고 상태(캐시·차단·속도제한·호출기록)를 초기화한다."""
    la.reset_state()
    CFG.clear()
    CFG.update(cfg)
    CALLS.clear()
    CLOCK[0] = 1000.0
    la._get = lambda name, default="": CFG.get(name, default)
    la._now = lambda: CLOCK[0]
    la.LOG_PATH = _tmp / "tier_b.jsonl"

    def fake_post(url, headers, payload, timeout):
        CALLS.append({"url": url, "headers": headers, "payload": payload, "timeout": timeout})
        return handler(url, headers, payload)

    la._http_post = fake_post


def which(url):
    return "cf" if "cloudflare" in url else "groq"


def ask(q, key="s1", lang=None, ai=True):
    return la.free_answer(q, lang or ("zh" if any("\u4e00" <= c <= "\u9fff" for c in q) else "ko"), key=key, ai_enabled=ai)


def hist(q):
    return [{"role": "user", "text": q}]


UNRELATED = "한국에서 은행 계좌 만드는 방법 알려줘"  # FAQ 와 무관 + 학교 고유 정보 아님
try:
    # --- 기본은 꺼짐: 동작이 예전과 똑같다
    setup({}, lambda *a: (_ for _ in ()).throw(AssertionError("꺼져 있는데 HTTP 호출됨")))
    check("LLM_ENABLED 기본값은 꺼짐", la.is_enabled() is False)
    check("꺼져 있으면 free_answer 는 None 이고 호출 없음", ask("오늘 날씨 어때") is None and not CALLS)
    e_off = build_entry("오늘 날씨 어때", hist("오늘 날씨 어때"), index)
    top = index.search("오늘 날씨 어때", lang="ko", top_k=3)
    check("꺼짐: 기존 none 항목과 키가 같다(ai/template 흔적 없음)",
          e_off["kind"] == "none" and set(e_off) == {"role", "kind", "best", "suggestions", "candidates"}, sorted(e_off))
    check("꺼짐: best·후보가 검색 결과 그대로",
          e_off["best"] == (top[0].score if top else None) and e_off["candidates"] == [(c.score, c.faq.id, c.faq.question_ko) for c in top])
    m_off = build_entry("휴학 신청은 언제 해요?", hist("휴학 신청은 언제 해요?"), index)
    check("꺼짐: FAQ 매칭(Tier A)은 그대로", m_off["kind"] == "match" and m_off["faq"].id == "F01")
    for val, want in [("on", True), ("TRUE", True), ("1", True), ("off", False), ("", False), ("0", False), ("no", False), ("false", False)]:
        CFG["LLM_ENABLED"] = val
        check(f"LLM_ENABLED={val!r} → {want}", la.is_enabled() is want)

    # --- 켜짐 + Cloudflare 만 설정: 기본 흐름
    setup(CF_ONLY, lambda url, h, p: cf_ok())
    e = build_entry("오늘 날씨 어때", hist("오늘 날씨 어때"), index, session_key="a")
    check("FAQ 에 없으면 kind=ai", e["kind"] == "ai", e.get("kind"))
    check("ai 항목: 답변 문장·모델 저장(재실행 때 다시 호출하지 않음)",
          e.get("text") == "클라우드플레어 답변이에요" and e.get("model") == "@cf/google/gemma-4-26b-a4b-it", e)
    check("ai 항목: best/suggestions/candidates 유지", {"best", "suggestions", "candidates"} <= set(e))
    check("ai 항목에는 출처 정보(faq/score/method)가 없다", not ({"faq", "score", "method"} & set(e)))
    c = CALLS[0]
    check("Cloudflare URL(계정·모델 경로)", c["url"] == "https://api.cloudflare.com/client/v4/accounts/acc123/ai/run/@cf/google/gemma-4-26b-a4b-it", c["url"])
    check("Bearer 헤더", c["headers"].get("Authorization") == f"Bearer {TOKEN}")
    pl = c["payload"]
    check("payload: messages[system,user] / max_tokens 1000 / thinking 끔",
          [m["role"] for m in pl["messages"]] == ["system", "user"] and pl["max_tokens"] == 1000
          and pl["chat_template_kwargs"] == {"enable_thinking": False}, pl)
    check("시스템 프롬프트(모르면 모른다·HiKorea·공식 사이트)",
          pl["messages"][0]["content"] == la.build_system_prompt("@cf/google/gemma-4-26b-a4b-it") and "HiKorea" in la.SYSTEM_PROMPT
          and "www.kyungnam.ac.kr" in la.SYSTEM_PROMPT and "不要编造" in la.SYSTEM_PROMPT)
    check("시간 초과 15초", c["timeout"] == 15)
    check("같은 항목을 다시 그려도(rerun) 호출이 늘지 않는다", len(CALLS) == 1)
    e_zh = build_entry("今天天气怎么样", hist("今天天气怎么样"), index, session_key="a")
    check("중국어 질문도 ai", e_zh["kind"] == "ai")

    # --- 응답 형식 방어
    setup(CF_ONLY, lambda url, h, p: {"result": {"response": "<think>x</think>옛 형식 답변"}, "success": True})
    r = ask(UNRELATED)
    check("result.response 형식·<think> 제거", r and r["kind"] == "ai" and r["text"] == "옛 형식 답변", r)
    setup(CF_ONLY, lambda url, h, p: {"result": {"choices": [{"message": {"content": "  "}}]}, "success": True})
    check("빈 답변은 실패 처리", ask(UNRELATED)["kind"] == "unavailable")
    setup(CF_ONLY, lambda url, h, p: cf_ok())
    r = ask(UNRELATED)
    check("neurons 기록", r["neurons"] == 12.5 and r["provider"] == "cloudflare", r)

    # --- 개인정보 가리기
    check("전화번호", "[NUMBER]" in la.mask_pii("전화 010-1234-5678") and "1234" not in la.mask_pii("전화 010-1234-5678"))
    check("국제전화(+82, +86)", "[NUMBER]" in la.mask_pii("+82 10 1234 5678") and "5678" not in la.mask_pii("+86 138 0013 8000"))
    check("붙여 쓴 전화·학번(8~11자리)", la.mask_pii("学号20201234") == "学号[NUMBER]" and la.mask_pii("13800138000") == "[NUMBER]")
    check("이메일", la.mask_pii("a.b+c@kyungnam.ac.kr 로") == "[EMAIL] 로")
    check("날짜·일반 숫자·학년은 남긴다", la.mask_pii("2026-10-28 마감 3월 15일 10시 2학년") == "2026-10-28 마감 3월 15일 10시 2학년")
    check("날짜 옆의 학번도 가린다", la.mask_pii("학번 20201234 2026-10-28") == "학번 [NUMBER] 2026-10-28")
    q_pii = "내 전화 010-1234-5678 학번 20201234 메일 a@b.com 인데 " + UNRELATED
    setup(CF_ONLY, lambda url, h, p: cf_ok())
    ask(q_pii)
    sent = CALLS[0]["payload"]["messages"][1]["content"]
    check("전송 문장에 개인정보 없음", not any(x in sent for x in ("1234", "20201234", "a@b.com")) and "[NUMBER]" in sent and "[EMAIL]" in sent, sent)
    log_text = (_tmp / "tier_b.jsonl").read_text(encoding="utf-8")
    check("로그에도 가려진 질문만 있고 키·토큰은 없다", "20201234" not in log_text and "a@b.com" not in log_text and TOKEN not in log_text and "Bearer" not in log_text)
    rec = json.loads(log_text.strip().splitlines()[-1])
    check("로그 필드(시각·질문·답변·모델·best·neurons)", {"ts", "question", "answer", "model", "best", "neurons"} <= set(rec) and rec["neurons"] == 12.5 and rec["model"], rec)
    setup(CF_ONLY, lambda url, h, p: cf_ok())
    check("숫자·이모지뿐인 입력은 보내지 않는다", ask("1234567890") is None and ask("😀😀😀") is None and not CALLS)

    # --- 학교 고유 정보 질문은 LLM 을 부르지 않고 고정 안내
    school_yes = ["学校图书馆几点开门", "国际处的电话是多少", "기숙사 비용 얼마예요", "등록금 납부 마감일이 언제예요",
                  "奖学金什么时候截止", "경남대 식당 어디에 있어요", "留学生服务中心的办公时间", "宿舍费多少钱", "补退选的截止日期是哪天",
                  "체육관 이용시간이 어떻게 돼요", "학교 도서관 몇 시까지 해요"]
    school_no = ["韩国签证延期要多少钱", "学校生活怎么样", "오늘 날씨 어때", "도서관이 좋아요?", "怎么在韩国办手机卡",
                 "几点了", UNRELATED, "경남 지역 날씨 어때", "학교 가는 길에 비가 와요", "휴학하면 뭐 해야 돼요", "今天天气怎么样", "학교 다니는 게 힘들어요", "宿舍好住吗"]
    check("학교 고유 정보 질문 판별(예)", all(la.looks_school_specific(q) for q in school_yes), [q for q in school_yes if not la.looks_school_specific(q)])
    check("일반 질문은 판별 안 됨(아니오)", not any(la.looks_school_specific(q) for q in school_no), [q for q in school_no if la.looks_school_specific(q)])
    setup(CF_ONLY, lambda *a: (_ for _ in ()).throw(AssertionError("템플릿 질문에서 HTTP 호출됨")))
    check("템플릿 질문은 LLM 호출 없이 template", all(ask(q) == {"kind": "template"} for q in school_yes) and not CALLS)
    # FAQ 에 매칭되는 문장이면 Tier A 가 먼저이므로, 매칭 안 되는 문장으로 확인한다
    q_t = next(q for q in school_yes if index.answer(q, lang="zh" if any("\u4e00" <= c <= "\u9fff" for c in q) else "ko") is None)
    e_t = build_entry(q_t, hist(q_t), index)
    check("template 항목은 none 이고 AI 항목이 아니다(출처 없음)", e_t["kind"] == "none" and e_t.get("template") is True and "text" not in e_t, e_t)
    check("템플릿 문구 한/중", STRINGS["ko"]["school_fact_template"] == "이 정보는 FAQ에 아직 없어요. 학교 공식 페이지나 해당 사무실에 직접 확인해 주세요."
          and STRINGS["zh"]["school_fact_template"] == "FAQ里还没有这条信息，请向学校官网或相关办公室确认。")
    setup(CF_ONLY, lambda url, h, p: cf_ok())
    ask("韩国签证延期要多少钱")
    check("학교 단어 없는 일반 질문은 LLM 으로 간다", len(CALLS) == 1)
    check("FAQ 에 있는 질문은 Tier A 그대로(LLM 호출 없음)",
          build_entry("휴학 신청은 언제 해요?", hist("x"), index)["kind"] == "match" and len(CALLS) == 1)

    # --- 캐시
    setup(CF_ONLY, lambda url, h, p: cf_ok())
    a1 = ask(UNRELATED)
    a2 = ask(UNRELATED)
    a3 = ask(UNRELATED + "?!")
    check("같은 질문(문장부호만 달라도)은 캐시로 응답, 호출 1번", len(CALLS) == 1 and a1["text"] == a2["text"] == a3["text"], len(CALLS))

    # --- 429 → 두 번째 제공자 폴백 + 차단기(60초)
    def h429(url, h, p):
        if which(url) == "cf":
            raise la.ProviderError(429)
        return groq_ok()
    setup(BOTH, h429)
    r = ask(UNRELATED)
    check("429 → groq 로 폴백", r["kind"] == "ai" and r["provider"] == "groq" and r["model"] == "openai/gpt-oss-120b" and [which(c["url"]) for c in CALLS] == ["cf", "groq"], r)
    gp = CALLS[1]["payload"]
    check("groq 요청 형식(OpenAI 호환, Bearer)", CALLS[1]["url"] == la.GROQ_URL and gp["model"] == "openai/gpt-oss-120b"
          and gp["messages"][0]["role"] == "system" and CALLS[1]["headers"]["Authorization"] == f"Bearer {GKEY}")
    ask("다른 질문입니다 학교 밖 생활 팁 알려줘")
    check("차단기: 60초 안에는 cloudflare 를 건너뛴다", [which(c["url"]) for c in CALLS][2:] == ["groq"], [which(c["url"]) for c in CALLS])
    CLOCK[0] += 61
    ask("세 번째 다른 질문이에요 병원 가는 법")
    check("60초 지나면 cloudflare 를 다시 시도", which(CALLS[3]["url"]) == "cf", [which(c["url"]) for c in CALLS])
    log_text = (_tmp / "tier_b.jsonl").read_text(encoding="utf-8")
    check("로그에 groq 키 없음", GKEY not in log_text and TOKEN not in log_text)

    for label, exc in [("5xx", la.ProviderError(503)), ("시간 초과", la.ProviderError(None, "timeout"))]:
        def hx(url, h, p, exc=exc):
            if which(url) == "cf":
                raise exc
            return groq_ok()
        setup(BOTH, hx)
        r = ask(UNRELATED)
        check(f"{label} → groq 폴백", r["kind"] == "ai" and r["provider"] == "groq" and len(CALLS) == 2, r)
        ask("또 다른 질문이에요 은행 어플 추천")
        check(f"{label}는 차단기를 켜지 않는다(다음 질문도 cloudflare 먼저)", [which(c["url"]) for c in CALLS][2:] == ["cf", "groq"])

    # --- 제공자가 하나뿐일 때: 재시도 1번까지
    seq = iter([la.ProviderError(500), None])

    def h_retry(url, h, p):
        err = next(seq)
        if err:
            raise err
        return cf_ok()
    setup(CF_ONLY, h_retry)
    r = ask(UNRELATED)
    check("5xx 한 번 → 같은 제공자에 재시도해서 성공(총 2번)", r["kind"] == "ai" and len(CALLS) == 2, len(CALLS))

    def h_down(url, h, p):
        raise la.ProviderError(500)
    setup(CF_ONLY, h_down)
    r = ask(UNRELATED)
    check("계속 실패하면 총 2번까지만 시도하고 unavailable", r["kind"] == "unavailable" and len(CALLS) == 2, len(CALLS))
    setup(BOTH, h_down)
    r = ask(UNRELATED)
    check("둘 다 실패해도 총 2번까지만", r["kind"] == "unavailable" and len(CALLS) == 2, len(CALLS))

    def h_only429(url, h, p):
        raise la.ProviderError(429)
    setup(CF_ONLY, h_only429)
    r1 = ask(UNRELATED)
    n1 = len(CALLS)
    r2 = ask("다른 질문 한국 병원 예약 방법")
    check("429 는 재시도 없이 1번, 이후 60초는 호출 자체를 안 함", r1["kind"] == "unavailable" and n1 == 1 and len(CALLS) == 1 and r2["kind"] == "unavailable", (n1, len(CALLS)))
    e_f = build_entry(UNRELATED, hist("x"), index)
    check("실패하면 기존 none 항목 + ai_failed 표시", e_f["kind"] == "none" and e_f.get("ai_failed") is True and not e_f.get("template"), e_f)
    setup({"LLM_ENABLED": "on"}, lambda *a: (_ for _ in ()).throw(AssertionError("키가 없는데 호출됨")))
    check("켜졌지만 키가 없으면 unavailable(호출 없음)", ask(UNRELATED)["kind"] == "unavailable" and not CALLS)
    setup({**BOTH, "LLM_PROVIDER": "groq"}, lambda url, h, p: groq_ok() if which(url) == "groq" else cf_ok())
    check("LLM_PROVIDER=groq 이면 groq 가 먼저", ask(UNRELATED)["provider"] == "groq" and len(CALLS) == 1)

    # --- 속도 제한 (세션 키 단위, 기본 1분 2회)
    setup(CF_ONLY, lambda url, h, p: cf_ok())
    r = [ask(f"서로 다른 질문 {w} 알려줘", key="s1") for w in ("은행", "병원", "버스")]
    check("1분 2회 초과는 호출 없이 거절", [x["kind"] for x in r] == ["ai", "ai", "unavailable"] and r[2]["reason"] == "rate_limited" and len(CALLS) == 2, r)
    check("다른 세션은 영향 없음", ask("서로 다른 질문 지하철 알려줘", key="s2")["kind"] == "ai")
    CLOCK[0] += 61
    check("1분 뒤 다시 허용", ask("서로 다른 질문 택시 알려줘", key="s1")["kind"] == "ai")
    CFG["LLM_RATE_PER_MIN"] = "1"
    CLOCK[0] += 61
    ask("한도 변경 질문 하나 알려줘", key="s3")
    check("LLM_RATE_PER_MIN 설정 반영", ask("한도 변경 질문 둘 알려줘", key="s3")["reason"] == "rate_limited")

    # --- AI 항목은 후속(더 알려줘·번역) 미지원: 이전 FAQ 답변을 엉뚱하게 다시 보여주지 않는다
    setup(CF_ONLY, lambda url, h, p: cf_ok())
    ai_e = build_entry(UNRELATED, hist(UNRELATED), index)
    h2 = [{"role": "user", "text": "휴학 신청은 언제 해요?"}, m_off, {"role": "user", "text": UNRELATED}, ai_e, {"role": "user", "text": "더 자세히"}]
    check("AI 답변 뒤 '더 자세히' → 안내 문구", build_entry("더 자세히", h2, index) == {"role": "assistant", "kind": "talk", "key": "talk_ai_followup"})
    check("AI 답변 뒤 '중국어로' → 안내 문구", build_entry("중국어로", h2, index)["key"] == "talk_ai_followup")
    h3 = h2[:2] + [{"role": "user", "text": "더 자세히"}]
    check("FAQ 답변 뒤 후속 요청은 예전처럼 동작", build_entry("더 자세히", h3, index)["kind"] == "match")

    # --- 사용자 토글(ai_enabled): 서버가 켜져 있어도 사용자가 안 켜면 예전(FAQ 전용) 동작 그대로
    def _boom(*a):
        raise AssertionError("토글이 꺼져 있는데 HTTP 호출됨")

    setup({}, _boom)
    check("is_available: 설정 없음 → False", la.is_available() is False)
    CFG.update({"LLM_ENABLED": "on"})
    check("is_available: 스위치만 켜고 키 없음 → False(토글 비활성)", la.is_available() is False)
    setup({"CLOUDFLARE_ACCOUNT_ID": "acc123", "CLOUDFLARE_API_TOKEN": TOKEN}, _boom)
    check("is_available: 키만 있고 스위치 꺼짐 → False(운영자 스위치 우선)", la.is_available() is False)
    setup(CF_ONLY, _boom)
    check("is_available: 스위치 on + Cloudflare 키 → True", la.is_available() is True)
    setup({"LLM_ENABLED": "on", "GROQ_API_KEY": GKEY}, _boom)
    check("is_available: 스위치 on + Groq 키만 → True", la.is_available() is True)
    setup({"LLM_ENABLED": "on", "CLOUDFLARE_ACCOUNT_ID": "acc123"}, _boom)
    check("is_available: 계정 ID 만 있고 토큰 없음 → False", la.is_available() is False)
    check("is_available 는 bool 만 돌려주고 비밀값을 노출하지 않는다", isinstance(la.is_available(), bool))

    setup(CF_ONLY, _boom)
    check("서버 켜짐 + 토글 꺼짐(ai_enabled=False): free_answer 는 None, 호출 없음", ask(UNRELATED, ai=False) is None and not CALLS)
    check("ai_enabled 기본값은 False(명시하지 않으면 AI 를 부르지 않는다)",
          la.free_answer(UNRELATED, "ko", key="s1") is None and not CALLS)
    e_tog_off = build_entry("오늘 날씨 어때", hist("오늘 날씨 어때"), index, ai_enabled=False)
    e_tog_dflt = _build_entry("오늘 날씨 어때", hist("오늘 날씨 어때"), index)
    top_t = index.search("오늘 날씨 어때", lang="ko", top_k=3)
    check("서버 켜짐 + 토글 꺼짐: build_entry 는 기존 none 항목과 키·내용이 같고 호출 없음",
          e_tog_off == e_tog_dflt and e_tog_off["kind"] == "none"
          and set(e_tog_off) == {"role", "kind", "best", "suggestions", "candidates"}
          and e_tog_off["best"] == (top_t[0].score if top_t else None) and not CALLS, sorted(e_tog_off))
    check("서버 켜짐 + 토글 꺼짐: 학교 고유 정보 질문도 template 없이 기존 none", "template" not in build_entry(q_t, hist(q_t), index, ai_enabled=False) and not CALLS)
    m_tog = build_entry("휴학 신청은 언제 해요?", hist("휴학 신청은 언제 해요?"), index, ai_enabled=False)
    check("토글 꺼짐: FAQ 매칭(Tier A)은 그대로", m_tog["kind"] == "match" and m_tog["faq"].id == "F01")

    setup(CF_ONLY, lambda url, h, p: cf_ok())
    check("토글 켜짐 + 서버 켜짐 → ai", build_entry("오늘 날씨 어때", hist("오늘 날씨 어때"), index, ai_enabled=True)["kind"] == "ai" and len(CALLS) == 1)
    check("같은 질문을 토글 꺼짐으로 보내면 캐시가 있어도 AI 를 쓰지 않는다(호출·캐시 응답 없음)",
          build_entry("오늘 날씨 어때", hist("오늘 날씨 어때"), index, ai_enabled=False)["kind"] == "none" and len(CALLS) == 1)
    check("다시 켜면 캐시 적중: 호출이 늘지 않는다", build_entry("오늘 날씨 어때", hist("오늘 날씨 어때"), index, ai_enabled=True)["kind"] == "ai" and len(CALLS) == 1)
    setup({}, _boom)
    check("서버 꺼짐 + 토글 켜짐(ai_enabled=True): 호출 없이 기존 none", build_entry("오늘 날씨 어때", hist("오늘 날씨 어때"), index, ai_enabled=True)["kind"] == "none" and not CALLS)
    setup(CF_ONLY, lambda url, h, p: cf_ok())
    r_a, r_b, r_c = (ask(f"세션 한도 확인 질문 {w} 알려줘", key="tog") for w in ("가", "나", "다"))
    check("토글 켜짐에서도 세션 속도 제한(1분 2회)은 그대로", [r_a["kind"], r_b["kind"], r_c["kind"]] == ["ai", "ai", "unavailable"] and r_c["reason"] == "rate_limited")

    # --- 화면 코드와 문구(토글)
    app_src = Path("app.py").read_text(encoding="utf-8")
    app_ast = ast.parse(app_src)
    bcalls = [n for n in ast.walk(app_ast) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "build_entry"]
    check("app.py: build_entry 에 ai_enabled 를 명시해 넘긴다", len(bcalls) == 1 and any(k.arg == "ai_enabled" for k in bcalls[0].keywords))
    tcalls = [n for n in ast.walk(app_ast) if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "toggle"]
    check("app.py: st.toggle 이 있고 disabled 인자(서버 미설정이면 비활성)를 쓴다", len(tcalls) == 1 and any(k.arg == "disabled" for k in tcalls[0].keywords))
    sb_toggles = [n for w in ast.walk(app_ast) if isinstance(w, ast.With) and any(
        isinstance(i.context_expr, ast.Attribute) and i.context_expr.attr == "sidebar" for i in w.items)
        for n in ast.walk(w) if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "toggle"]
    check("app.py: AI 토글은 사이드바 블록 밖, 채팅 입력창(st.chat_input)보다 먼저 같은 하단 영역(st.bottom)에 그린다",
          len(tcalls) == 1 and not sb_toggles and "st.bottom" in app_src
          and tcalls[0].lineno < next(n for n in ast.walk(app_ast) if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "chat_input").lineno)
    check("app.py: 토글 상태는 session_state 에 두고 모듈 전역 변수에 의존하지 않는다", "ai_on" in app_src and "LLM_ENABLED" not in app_src)
    check("토글 문구 한/중(요청한 문구 그대로)", STRINGS["ko"]["ai_toggle"] == "🤖 AI 대화 켜기 (FAQ에 없는 질문에 AI가 답해요)"
          and STRINGS["zh"]["ai_toggle"] == "🤖 开启AI对话（FAQ里没有的问题由AI回答）")
    check("미설정 캡션 한/중", STRINGS["ko"]["ai_not_configured"] == "AI 기능이 서버에 설정되지 않았습니다" and STRINGS["zh"]["ai_not_configured"] == "服务器未配置AI功能")
    check("도움말: 확인되지 않은 답변 경고", "확인되지 않" in STRINGS["ko"]["ai_toggle_help"] and "未经核实" in STRINGS["zh"]["ai_toggle_help"])
    check("켤 때 안내: 미확인·개인정보 금지·외부 AI 서비스(Cloudflare Workers AI)",
          all(w in STRINGS["ko"]["ai_on_notice"] for w in ("확인되지 않", "개인정보", "외부 AI 서비스", "Cloudflare Workers AI"))
          and all(w in STRINGS["zh"]["ai_on_notice"] for w in ("未经确认", "个人信息", "外部AI服务", "Cloudflare Workers AI")))

    # --- 문구 키 점검: 코드에서 t("키") 로 부르는 모든 키가 한/중 사전에 정확히 있다(없으면 화면에 키 이름이 그대로 나온다)
    used_keys = set()
    for src_name in ("app.py", "chat_logic.py"):
        for n in ast.walk(ast.parse(Path(src_name).read_text(encoding="utf-8"))):
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "t" and n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                used_keys.add(n.args[0].value)
    check("코드의 t('키') 호출 키 전부가 ko·zh 사전에 있다", used_keys and all(k in STRINGS["ko"] and k in STRINGS["zh"] for k in used_keys),
          sorted(k for k in used_keys if k not in STRINGS["ko"] or k not in STRINGS["zh"]))
    check("AI 토글 키 4개가 ko·zh 사전에 있고 값이 키 이름과 다르며 비어 있지 않다",
          all(STRINGS[lg].get(k) and STRINGS[lg][k] != k for lg in ("ko", "zh") for k in ("ai_toggle", "ai_toggle_help", "ai_not_configured", "ai_on_notice")))
    check("i18n 값이 키 이름과 같은 항목이 없다(번역 누락 방지)", not [(lg, k) for lg in ("ko", "zh") for k, v in STRINGS[lg].items() if v == k])
    _ast_app = ast.parse(Path("app.py").read_text(encoding="utf-8"))
    _lines = {getattr(n, "name", None) or n.func.id: n.lineno for n in _ast_app.body
              if isinstance(n, ast.FunctionDef) and n.name == "_reload_stale_local_modules"}
    _call_ln = next((n.lineno for n in _ast_app.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                     and getattr(n.value.func, "id", None) == "_reload_stale_local_modules"), None)
    _from_i18n = next((n.lineno for n in _ast_app.body if isinstance(n, ast.ImportFrom) and n.module == "i18n"), None)
    check("app.py: 서버를 켜 둔 채 .py 가 바뀌어도 옛 i18n 이 남지 않도록 'from i18n import' 앞에서 모듈을 다시 불러온다",
          _lines and _call_ln and _from_i18n and _call_ln < _from_i18n, (_lines, _call_ln, _from_i18n))

    # --- 화면 코드와 문구
    app_tree = ast.parse(Path("app.py").read_text(encoding="utf-8"))
    render_ai_fn = next(n for n in ast.walk(app_tree) if isinstance(n, ast.FunctionDef) and n.name == "render_ai")
    used = {n.id for n in ast.walk(render_ai_fn) if isinstance(n, ast.Name)} | {n.value for n in ast.walk(render_ai_fn) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    check("render_ai: ai_label·ai_nudge 사용, render_source 호출 없음", {"ai_label", "ai_nudge"} <= used and "render_source" not in used, used)
    check("ko/zh 문구 키가 서로 같다", set(STRINGS["ko"]) == set(STRINGS["zh"]), set(STRINGS["ko"]) ^ set(STRINGS["zh"]))
    check("ai_label 한/중 문구", STRINGS["ko"]["ai_label"] == "🤖 AI 자율 답변 · 확인되지 않음 (FAQ에 없는 질문이라 AI가 직접 답했어요)"
          and STRINGS["zh"]["ai_label"] == "🤖 AI自主回答，未经确认（FAQ中没有这个问题，由AI直接回答）")
    check("ai_nudge 한/중 문구(공식 사이트 안내)", "www.kyungnam.ac.kr" in STRINGS["ko"]["ai_nudge"] and "www.kyungnam.ac.kr" in STRINGS["zh"]["ai_nudge"])
    check("ai_unavailable 존재", STRINGS["ko"].get("ai_unavailable") and STRINGS["zh"].get("ai_unavailable"))
    check("'모든 답변에 출처' 같은 거짓이 되는 문구 제거", "모든 답변" not in STRINGS["ko"]["chips"] and "回答均" not in STRINGS["zh"]["chips"])

    # ============================================================ [13] 사용자 보고(2026-10-29) 수정 점검
    print("[13] 짧은·무관한 질문 가드 / 오늘 날짜·모델명 프롬프트 / URL 안전 렌더링 / 中文 라벨")
    from datetime import date as _date

    import linkify
    from chat_logic import AI_MIN_CONTENT_SCORE, AI_STRONG_SCORE, is_confident_match

    ZW = "你是什\u200b\u200b么模型"  # 사용자가 실제로 보낸 질문(보이지 않는 글자 포함)
    check("normalize: 보이지 않는 글자(ZWSP·BOM 등)를 지운다", normalize(ZW) == normalize("你是什么模型") and "\u200b" not in normalize(ZW))
    check("normalize: 일반 질문은 그대로", normalize("休学怎么办") == normalize("休学怎么办"))

    # --- 가드: AI 가 켜져 있을 때만 적용
    off = _build_entry("你是什么模型", hist("你是什么模型"), index, ai_enabled=False)
    check("가드는 AI 꺼짐에서는 적용되지 않는다(예전 동작 그대로: FAQ 매칭)", off["kind"] == "match", off.get("kind"))
    for q in ("你是什么模型", ZW, "你是谁", "今天几号", "今天星期几", "今天是什么日子", "韩国手机卡怎么办"):
        setup(CF_ONLY, lambda url, h, p: cf_ok("테스트 답변"))
        e = build_entry(q, hist(q), index, session_key="g")
        check(f"가드(AI 켜짐): {q!r} 는 FAQ 에 잘못 붙지 않고 AI 로 간다", e["kind"] == "ai" and len(CALLS) == 1, (e.get("kind"), e.get("faq") and e["faq"].id))
    check("가드: 약한 일치의 '혹시 이런 질문인가요?' 제안은 걸러진다", not build_entry("你是什么模型", hist("x"), index, session_key="g2")["suggestions"])
    # 진짜 FAQ 질문은 가드를 통과한다(잃는 것 없음)
    lost = []
    for f in faqs:
        for lg, qtxt in (("ko", f.question_ko), ("zh", f.question_zh)):
            if not qtxt:
                continue
            m = index.answer(qtxt, lang=lg)
            if m is None or not is_confident_match(qtxt, m, lg):
                lost.append((f.id, lg, qtxt, m and round(m.score, 2)))
    check("가드: 모든 FAQ 자기 질문(ko/zh 질문)은 가드를 통과한다", not lost, lost[:5])
    for q, fid in (("休学怎么办", "F01"), ("휴학 신청은 언제 해요?", "F01")):
        setup(CF_ONLY, lambda url, h, p: cf_ok())
        e = build_entry(q, hist(q), index, session_key="g3")
        check(f"가드: 진짜 FAQ 질문 {q!r} 은 그대로 매칭({fid}), AI 호출 없음", e["kind"] == "match" and e["faq"].id == fid and not CALLS, (e.get("kind"), CALLS and len(CALLS)))
    check("가드 기준값(강한 일치 0.65 / 알맹이 일치 0.40)", (AI_STRONG_SCORE, AI_MIN_CONTENT_SCORE) == (0.65, 0.40))

    # --- 오늘 날짜(Asia/Seoul)·모델명이 시스템 프롬프트에 들어간다
    setup(CF_ONLY, lambda url, h, p: cf_ok())
    ask(UNRELATED)
    sysmsg = CALLS[0]["payload"]["messages"][0]["content"]
    d0 = la._today_kst()
    want_today = f"{d0.year}年{d0.month}月{d0.day}日，星期{'一二三四五六日'[d0.weekday()]}"
    check("시스템 프롬프트에 오늘 날짜(한국 시간)·요일", want_today in sysmsg, sysmsg[:120])
    check("_today_kst 는 UTC+9 기준", la.KST.utcoffset(None).total_seconds() == 9 * 3600)
    check("build_system_prompt(2026-10-29) = 2026年10月29日，星期四", "2026年10月29日，星期四" in la.build_system_prompt("m", _date(2026, 10, 29)))
    check("시스템 프롬프트: 설정된 모델 ID 를 알려 주는 문구", "具体模型名称为 @cf/google/gemma-4-26b-a4b-it" in sysmsg and "{model}" not in sysmsg and "{today}" not in sysmsg)
    check("시스템 프롬프트: 실시간 정보(날씨·뉴스)는 모른다고 말하게 한다", "天气" in sysmsg and "新闻" in sysmsg and "无法获取" in sysmsg)
    check("시스템 프롬프트: 완결된 문장·질문자 언어·짧지만 도움이 되게·학교 정보를 지어내지 않기",
          all(w in sysmsg for w in ("完整的句子", "提问者使用的语言", "简短但有帮助", "不要编造")) and "庆南大学" in sysmsg and "HiKorea" in sysmsg)
    CFG["LLM_MODEL"] = "@cf/openai/gpt-oss-120b"
    la.reset_state()
    CALLS.clear()
    ask(UNRELATED)
    pl2 = CALLS[0]["payload"]
    check("LLM_MODEL 을 바꾸면 URL·프롬프트의 모델명·추론 옵션이 따라간다",
          CALLS[0]["url"].endswith("/ai/run/@cf/openai/gpt-oss-120b") and "具体模型名称为 @cf/openai/gpt-oss-120b" in pl2["messages"][0]["content"]
          and "chat_template_kwargs" not in pl2 and pl2.get("reasoning", {}).get("effort") == "low", pl2.get("reasoning"))
    CFG.pop("LLM_MODEL")

    # --- 답변이 잘리지 않게: max_tokens, 길이 제한으로 끊긴 답은 마지막 완결 문장까지
    setup(CF_ONLY, lambda url, h, p: cf_ok())
    ask(UNRELATED)
    check("max_tokens 1000 이상(생각 토큰 포함 여유)", CALLS[0]["payload"]["max_tokens"] == la.MAX_TOKENS >= 1000, CALLS[0]["payload"]["max_tokens"])
    cut = {"result": {"choices": [{"message": {"content": "첫 문장이에요. 두 번째 문장도 있어요. 세 번째는 끊"}, "finish_reason": "length"}]}, "success": True}
    setup(CF_ONLY, lambda url, h, p: cut)
    r = ask(UNRELATED)
    check("길이 제한으로 끊긴 답: 끊긴 마지막 조각은 버리고 완결 문장까지", r["kind"] == "ai" and r["text"] == "첫 문장이에요. 두 번째 문장도 있어요.", r)
    setup(CF_ONLY, lambda url, h, p: cf_ok("今天\u202f是\u200b 2026年10月29日。"))
    check("특수 공백(U+202F)·보이지 않는 글자 정리", ask(UNRELATED)["text"] == "今天 是 2026年10月29日。", None)

    # --- 날짜가 답에 들어갈 수 있으므로 캐시는 날짜별
    setup(CF_ONLY, lambda url, h, p: cf_ok())
    _t0 = la._today_kst
    try:
        la._today_kst = lambda: _date(2026, 10, 29)
        ask("今天几号", key="c1")
        ask("今天几号", key="c2")
        n_same = len(CALLS)
        la._today_kst = lambda: _date(2026, 10, 30)
        ask("今天几号", key="c3")
        n_next = len(CALLS)
    finally:
        la._today_kst = _t0
    check("같은 날 같은 질문은 캐시(호출 1번), 다음 날은 새로 호출", n_same == 1 and n_next == 2, (n_same, n_next))

    # --- URL 안전 렌더링(linkify)
    sl = linkify.safe_links
    check("URL 뒤 전각 괄호·쉼표: 주소는 ASCII 만", sl("（www.kyungnam.ac.kr）确认") == "（[www.kyungnam.ac.kr](<https://www.kyungnam.ac.kr>)）确认", sl("（www.kyungnam.ac.kr）确认"))
    check("https 주소 + 전각 쉼표", sl("网址为 https://sugang.kyungnam.ac.kr，预选课") == "网址为 [https://sugang.kyungnam.ac.kr](<https://sugang.kyungnam.ac.kr>)，预选课")
    check("URL 뒤 한글 조사·한자", sl("www.kyungnam.ac.kr 에서") == "[www.kyungnam.ac.kr](<https://www.kyungnam.ac.kr>) 에서"
          and sl("https://a.kr/x한글") == "[https://a.kr/x](<https://a.kr/x>)한글")
    check("문장 끝 마침표·반각 괄호는 주소에서 뗀다", sl("see https://a.kr/x.") == "see [https://a.kr/x](<https://a.kr/x>)."
          and sl("(https://a.kr/x)") == "([https://a.kr/x](<https://a.kr/x>))")
    check("쿼리·괄호가 있는 주소는 그대로 유지", sl("https://a.kr/p?enc=Zm5jdDF8%2Fabc&x=1 ;") == "[https://a.kr/p?enc=Zm5jdDF8%2Fabc&x=1](<https://a.kr/p?enc=Zm5jdDF8%2Fabc&x=1>) ;")
    check("이미 마크다운 링크인 것은 다시 바꾸지 않는다(멱등)", sl(sl("（www.kyungnam.ac.kr）")) == sl("（www.kyungnam.ac.kr）") and sl("[x](<https://a.kr>)") == "[x](<https://a.kr>)")
    check("URL 이 없으면 글자 그대로", sl("URL 없는 글") == "URL 없는 글" and sl("") == "" and sl(None) is None)
    check("이메일·밑줄이 있는 주소 처리", sl("a@kyungnam.ac.kr") == "a@kyungnam.ac.kr" and sl("https://a.kr/a_b_c") == "[https://a.kr/a\\_b\\_c](<https://a.kr/a_b_c>)")
    hrefs_bad = []
    for f in faqs:
        for fld in (f.answer, f.answer_zh, f.source):
            for m in re.finditer(r"\]\(<([^>]*)>\)", sl(fld or "")):
                if re.search(r"[^\x00-\x7f]", m.group(1)) or "xn--" in m.group(1):
                    hrefs_bad.append((f.id, m.group(1)[:60]))
    check("모든 FAQ 의 답변·출처를 변환해도 링크 주소에 비ASCII 글자가 없다(faq.csv 는 그대로)", not hrefs_bad, hrefs_bad[:3])
    f23 = next(f for f in faqs if f.id == "F23")
    check("F23 답변: 选课网址가 쉼표·한자를 빼고 링크로", "[https://sugang.kyungnam.ac.kr](<https://sugang.kyungnam.ac.kr>)，预选课" in sl(f23.answer_zh))
    app_src2 = Path("app.py").read_text(encoding="utf-8")
    check("app.py: say·출처 줄·AI 안내·사용자 말풍선이 safe_links 를 거친다", app_src2.count("safe_links(") >= 5 and "from linkify import safe_links" in app_src2, app_src2.count("safe_links("))
    check("app.py: 서버를 켜 둔 채 바뀐 linkify.py 도 다시 불러온다", "linkify" in app_src2.split("_LOCAL_MODULES")[1].split("\n")[0])
    check("i18n: ai_nudge 의 URL 앞뒤에 공백(한/중)", " www.kyungnam.ac.kr " in STRINGS["ko"]["ai_nudge"] and " www.kyungnam.ac.kr " in STRINGS["zh"]["ai_nudge"])

    # --- 中文 라벨
    check("zh ai_label 정확한 문구(未经确认)", STRINGS["zh"]["ai_label"] == "🤖 AI自主回答，未经确认（FAQ中没有这个问题，由AI直接回答）")
    check("i18n 어디에도 '默认确认'(번역기가 바꾼 잘못된 문구)이 없다", not [(lg, k) for lg in STRINGS for k, v in STRINGS[lg].items() if "默认确认" in str(v)])
finally:
    la._get, la._http_post, la._now, la.LOG_PATH = _saved
    la.reset_state()
    import shutil

    shutil.rmtree(_tmp, ignore_errors=True)

print()
if FAILS:
    print(f"실패 {len(FAILS)}건: {FAILS}")
    sys.exit(1)
print("모두 통과")
