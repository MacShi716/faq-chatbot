# -*- coding: utf-8 -*-
"""화면이 실제로 동작하는지 확인하는 UI 스모크 테스트.

Streamlit 공식 테스트 하네스(AppTest)로 app.py 를 그대로 실행한다.
    python smoke_ui.py
"""

import sys

from streamlit.testing.v1 import AppTest

FAILS = []


def check(name, cond, detail=""):
    if cond:
        print(f"  OK   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        FAILS.append(name)


def all_text(at) -> str:
    parts = [m.value for m in at.markdown]
    parts += [c.value for c in at.caption]
    return "\n".join(parts)


def tree_strings(at):
    """화면 트리 전체(본문·사이드바·하단 고정 영역 st.bottom)의 모든 요소에서 문자열 값을 모은다.
    at.main / at.sidebar 에는 st.bottom 이 안 잡히므로 at._tree 의 모든 블록을 직접 돈다(label·help·placeholder·body·options 등)."""
    from google.protobuf.json_format import MessageToDict

    out = []

    def walk_value(v, key=""):
        if isinstance(v, str):
            if key != "id":  # 위젯 id 에는 key= 이름이 들어 있어 제외(문구가 아님)
                out.append(v)
        elif isinstance(v, dict):
            for k, x in v.items():
                walk_value(x, k)
        elif isinstance(v, list):
            for x in v:
                walk_value(x, key)

    def walk(node):
        if hasattr(node, "children"):
            for c in node.children.values():
                walk(c)
        elif hasattr(node, "proto"):
            if node.type == "html":  # 스타일 시트는 제외
                return
            walk_value(MessageToDict(node.proto))

    walk(at._tree)
    return out


def raw_key_hits(at, keys):
    """화면에 문구 키 이름이 그대로(문자열 전체가 키와 같게) 나온 곳. 정상이면 빈 리스트."""
    return sorted({x for x in tree_strings(at) if x.strip() in keys})


print("[1] 앱 기동 (기본 한국어)")
at = AppTest.from_file("app.py", default_timeout=60)
at.run()
check("예외 없음", not at.exception, at.exception)
check("한국어 제목", "학과 교무·생활" in "\n".join(x.value for x in at.title), [x.value for x in at.title])
check("사이드바 라디오 존재", len(at.radio) >= 1)
check("언어 전환 위젯 존재", len(at.get("segmented_control")) >= 1)
check("AI 대화 토글 존재(서버 미설정이면 비활성·꺼짐)", len(at.toggle) == 1 and at.toggle[0].value is False, [x.label for x in at.toggle])
check("AI 대화 토글은 사이드바·본문이 아니라 채팅 입력창과 같은 하단 영역(입력창 바로 위)에 있다",
      len(at.sidebar.toggle) == 0 and len(at.main.toggle) == 0 and len(at.chat_input) == 1
      and any(len(b.toggle) == 1 and len(b.chat_input) == 1 for b in at._tree.children.values()),
      (len(at.sidebar.toggle), len(at.main.toggle), len(at.toggle), len(at.chat_input)))

print("[2] 한국어 질문")
at.chat_input[0].set_value("휴학 신청은 언제 해요?").run()
check("예외 없음", not at.exception, at.exception)
text = all_text(at)
check("답변 표시", "F01" in text, text[:200])

print("[3] 중국어 질문")
at.chat_input[0].set_value("什么时候选课？").run()
check("예외 없음", not at.exception, at.exception)
text = all_text(at)
check("중국어 처리", "F04" in text, text[-200:])

print("[4] 화면 언어를 中文 으로 전환")
at.get("segmented_control")[0].set_value("zh")
at.run()
check("예외 없음", not at.exception, at.exception)
check("중국어 제목", "院系教务" in "\n".join(x.value for x in at.title), [x.value for x in at.title])
check("중국어 사이드바", "设置" in "\n".join(x.value for x in at.header), [x.value for x in at.header])

print("[5] 전환 후에도 질문 동작 + 중국어 답변 표시")
at.chat_input[0].set_value("怎么申请宿舍？").run()
check("예외 없음", not at.exception, at.exception)
text = all_text(at)
check("중국어 답변(待确认 → 未核实 배지)", "未核实的回答" in text and "确认日 未确认" in text, text[-300:])
check("한국어 원문 폴백 표시는 없음", "韩语原文" not in text, text[-300:])


print("[6] 캠퍼스맵 장소 질문 (중국어 화면 → 한국어 화면)")
MAP_URL = "https://inews.kyungnam.ac.kr/bbs/view.html?idxno=39517"
at.chat_input[0].set_value("法政馆在哪").run()
check("예외 없음", not at.exception, at.exception)
text = all_text(at)
check("중국어: 지도 번호와 링크", "地图 23 号" in text and MAP_URL in text, text[-300:])
at.get("segmented_control")[0].set_value("ko")
at.run()
at.chat_input[0].set_value("제1공학관 어디예요").run()
check("예외 없음", not at.exception, at.exception)
text = all_text(at)
check("한국어: 지도 번호와 링크", "캠퍼스맵 11번" in text and MAP_URL in text, text[-300:])
check("언어 전환 후 이전 답변도 한국어로 다시 표시", "캠퍼스맵 23번" in text, text[-300:])

print("[7] checked_at 비어 있으면 미확인 배지, 확인된 행은 배지 없음 (새 화면)")
UNV = "미확인 답변"
for q, expect_badge, label in [
    ("휴학 신청은 언제 해요?", True, "F01 待确认(checked_at 없음)"),
    ("한마상 어디예요", True, "F46 待确认(중문 명칭 추정)"),
    ("학과 사무실은 어디에 있어요?", True, "F10 待收集答案(자리표시자)"),
    ("제1공학관 어디예요", False, "F13 已确认(확인일 2026-10-28)"),
    ("법정관 어디예요", False, "지도 행 已确认"),
]:
    at7 = AppTest.from_file("app.py", default_timeout=60)
    at7.run()
    at7.chat_input[0].set_value(q).run()
    check("예외 없음: " + q, not at7.exception, at7.exception)
    text = all_text(at7)
    check(label + (" → 배지 있음" if expect_badge else " → 배지 없음"), (UNV in text) == expect_badge, text[-300:])

print("[8] Tier B: AI 자율 답변 화면 (HTTP 는 가짜, 실제 호출 없음)")
import re
import shutil
import tempfile
from pathlib import Path

import llm_answer as la

_saved = (la._get, la._http_post, la.LOG_PATH)
_tmp = Path(tempfile.mkdtemp(prefix="tierb_smoke_"))
CFG, CALLS, PAYLOADS = {}, [], []
MOCK_TEXT = "한국 은행 계좌는 신분증을 가지고 은행 지점에 가서 만들 수 있어요."
LABEL_KO, LABEL_ZH = "AI 자율 답변 · 확인되지 않음", "AI自主回答，未经确认"
ON = {"LLM_ENABLED": "on", "CLOUDFLARE_ACCOUNT_ID": "acc123", "CLOUDFLARE_API_TOKEN": "SECRET-TOKEN"}


def install(cfg, fail=False):
    la.reset_state()
    CFG.clear()
    CFG.update(cfg)
    CALLS.clear()
    PAYLOADS.clear()
    la._get = lambda name, default="": CFG.get(name, default)
    la.LOG_PATH = _tmp / "tier_b.jsonl"

    def fake_post(url, headers, payload, timeout):
        CALLS.append(url)
        PAYLOADS.append(payload)
        if fail:
            raise la.ProviderError(500)
        return {"result": {"choices": [{"message": {"content": MOCK_TEXT}}], "usage": {"neurons": 7}}, "success": True}

    la._http_post = fake_post


def new_app(ai=True):
    """새 세션. ai=True 면 서버에 AI 가 설정돼 있을 때 입력창 바로 위 'AI 대화 켜기' 토글을 사용자가 켠 상태로 시작한다."""
    a = AppTest.from_file("app.py", default_timeout=60)
    a.run()
    if ai and a.toggle and not a.toggle[0].disabled:
        a.toggle[0].set_value(True).run()
    return a


try:
    install({})  # 기본값: 꺼짐
    a8 = new_app()
    a8.chat_input[0].set_value("오늘 날씨 어때").run()
    text = all_text(a8)
    check("꺼짐: 예외 없음 + 기존 안내(AI 라벨·호출 없음)", not a8.exception and "죄송합니다" in text and LABEL_KO not in text and not CALLS, a8.exception or text[-200:])

    install(ON)
    a8 = new_app()
    a8.chat_input[0].set_value("오늘 날씨 어때").run()
    text = all_text(a8)
    check("켜짐: 예외 없음", not a8.exception, a8.exception)
    check("AI 라벨이 답변 앞에 표시", LABEL_KO in text and "FAQ에 없는 질문이라 AI가 직접 답했어요" in text, text[-300:])
    check("AI 답변 본문 표시", MOCK_TEXT in text)
    check("확인 유도 문구(공식 페이지) 표시", "www.kyungnam.ac.kr" in text and "정확하지 않을 수 있어요" in text)
    check("모델 이름 캡션", "모델: @cf/google/gemma-4-26b-a4b-it" in text)
    check("출처 줄(근거:)·FAQ id 없음", "근거:" not in text and "· FAQ F" not in text, text[-300:])
    check("미확인 배지(⚠️)는 FAQ 전용이라 없음", "미확인 답변" not in text)
    check("라벨 → 본문 → 안내 순서", text.index(LABEL_KO) < text.index(MOCK_TEXT) < text.index("정확하지 않을 수 있어요"))
    check("LLM 호출은 1번", len(CALLS) == 1, len(CALLS))
    a8.run()
    text = all_text(a8)
    check("화면이 다시 그려져도 호출이 늘지 않고 라벨·본문 유지", len(CALLS) == 1 and LABEL_KO in text and MOCK_TEXT in text, len(CALLS))

    a8.chat_input[0].set_value("더 자세히").run()
    check("AI 답변 뒤 '더 자세히' → 안내(이전 FAQ 를 다시 보여주지 않음)", not a8.exception and "다시 보여주거나 번역하는 기능이 없어요" in all_text(a8), a8.exception)

    a8.get("segmented_control")[0].set_value("zh")
    a8.run()
    text = all_text(a8)
    check("中文 전환: 이전 AI 답변도 中文 라벨로", not a8.exception and LABEL_ZH in text and "www.kyungnam.ac.kr" in text, a8.exception or text[-300:])
    a8.chat_input[0].set_value("今天天气怎么样").run()
    text = all_text(a8)
    check("中文 질문: AI 라벨·모델, 출처 줄 없음(依据 없음)", not a8.exception and text.count(LABEL_ZH) >= 2 and "模型：@cf/google" in text and "依据：" not in text, a8.exception or text[-300:])
    check("中文 칩 문구(출처는 FAQ 에만)", "AI回答另有标注" in text and "回答均附" not in text)

    # FAQ 에 있는 질문은 켜져 있어도 Tier A 그대로
    install(ON)
    a8 = new_app()
    a8.chat_input[0].set_value("휴학 신청은 언제 해요?").run()
    text = all_text(a8)
    check("켜짐 + FAQ 질문: FAQ 답변·출처, AI 라벨/호출 없음", "F01" in text and "근거:" in text and LABEL_KO not in text and not CALLS, text[-200:])

    # 학교 고유 정보 → 고정 안내(LLM 호출 없음, AI 라벨 없음, 출처 없음)
    install(ON)
    a8 = new_app()
    a8.get("segmented_control")[0].set_value("zh")
    a8.run()
    a8.chat_input[0].set_value("补退选的截止日期是哪天").run()
    text = all_text(a8)
    check("학교 고유 정보: 고정 안내, 호출 없음, AI 라벨·출处 없음",
          not a8.exception and "FAQ里还没有这条信息" in text and not CALLS and LABEL_ZH not in text and "依据：" not in text, a8.exception or text[-300:])

    # 실패 → 기존 none 화면 + AI 불가 안내
    install(ON, fail=True)
    a8 = new_app()
    a8.chat_input[0].set_value("오늘 날씨 어때").run()
    text = all_text(a8)
    check("LLM 장애: 기존 안내 + AI 답변 불가 문구, 라벨 없음", not a8.exception and "죄송합니다" in text and "AI 답변을 가져오지 못했어요" in text and LABEL_KO not in text, a8.exception or text[-300:])

    print("[9] AI 대화 토글 (사용자별 선택 · 기본 꺼짐 · 서버 미설정이면 비활성)")
    TOG_KO, TOG_ZH = "🤖 AI 대화 켜기 (FAQ에 없는 질문에 AI가 답해요)", "🤖 开启AI对话（FAQ里没有的问题由AI回答）"
    Q1, Q2, Q3 = "오늘 날씨 어때", "한국에서 은행 계좌 만드는 방법 알려줘", "한국 지하철 환승 방법 알려줘"
    install(ON)
    t9 = new_app(ai=False)
    tg = t9.toggle[0] if t9.toggle else None
    check("서버 설정됨: 토글 존재·기본 꺼짐·사용 가능", tg is not None and tg.value is False and not tg.disabled and tg.label == TOG_KO,
          tg and (tg.value, tg.disabled, tg.label))
    check("토글 도움말: 확인되지 않은 답변 경고", tg is not None and "확인되지 않은" in (tg.help or ""), tg and tg.help)
    check("꺼짐 상태에서는 안내 문구·토스트 없음", not t9.toast and "Cloudflare Workers AI" not in all_text(t9))
    t9.chat_input[0].set_value(Q1).run()
    text = all_text(t9)
    check("서버 켜짐 + 토글 꺼짐(기본): 기존 안내, AI 라벨 없음, LLM 호출 0번",
          not t9.exception and "죄송합니다" in text and LABEL_KO not in text and not CALLS, t9.exception or (len(CALLS), text[-200:]))
    t9.run()
    check("토글 꺼짐 + 화면 다시 그리기: 여전히 호출 0번", not CALLS)

    t9.toggle[0].set_value(True).run()
    text = all_text(t9)
    check("토글 켜기: 예외 없음·값 유지", not t9.exception and t9.toggle[0].value is True, t9.exception)
    check("켜는 순간 안내(토스트): 미확인·개인정보 금지·외부 AI 서비스",
          len(t9.toast) == 1 and all(w in t9.toast[0].value for w in ("확인되지 않", "개인정보", "Cloudflare Workers AI")), [x.value for x in t9.toast])
    check("켜 둔 동안 토글 아래 안내 유지", "외부 AI 서비스(Cloudflare Workers AI 등)" in text)
    check("켜기만 해서는 LLM 호출 없음, 앞서 만든 꺼짐 답변은 그대로(AI 라벨 없음)", not CALLS and "죄송합니다" in text and LABEL_KO not in text)
    t9.run()
    check("다시 그려도 안내 토스트는 반복되지 않는다(한 번만)", not t9.toast)
    t9.chat_input[0].set_value(Q2).run()
    text = all_text(t9)
    check("토글 켜짐: 같은 세션의 새 질문에 AI 라벨·본문, 호출 1번",
          not t9.exception and LABEL_KO in text and MOCK_TEXT in text and len(CALLS) == 1, t9.exception or (len(CALLS), text[-200:]))

    t9.toggle[0].set_value(False).run()
    text = all_text(t9)
    check("토글 끄기: 이전 AI 답변은 그대로 표시, 호출 늘지 않음(rerun 이 LLM 을 다시 부르지 않음)",
          not t9.exception and LABEL_KO in text and MOCK_TEXT in text and len(CALLS) == 1 and not t9.toast, t9.exception or len(CALLS))
    check("토글 끄면 토글 아래 안내 사라짐", "외부 AI 서비스(Cloudflare Workers AI 등)" not in text)
    t9.chat_input[0].set_value(Q3).run()
    text = all_text(t9)
    check("토글 다시 꺼짐: 새 질문은 기존 안내, 새 호출 없음", not t9.exception and len(CALLS) == 1 and text.count(LABEL_KO) == 1 and text.count("죄송합니다") == 2,
          t9.exception or (len(CALLS), text.count(LABEL_KO), text.count("죄송합니다")))

    t9.toggle[0].set_value(True).run()
    t9.get("segmented_control")[0].set_value("zh")
    t9.run()
    text = all_text(t9)
    check("화면 언어 전환(켜짐 상태): 토글 값 유지·中文 라벨", not t9.exception and t9.toggle[0].value is True and t9.toggle[0].label == TOG_ZH,
          t9.exception or (t9.toggle[0].value, t9.toggle[0].label))
    check("언어 전환 후에도 이전 AI 답변 유지, 호출 늘지 않음", LABEL_ZH in text and len(CALLS) == 1)
    check("中文 안내 문구", "请不要输入个人信息" in text and "外部AI服务" in text)
    t9.get("segmented_control")[0].set_value("ko")
    t9.run()
    check("다시 한국어: 토글 켜짐 유지", not t9.exception and t9.toggle[0].value is True and t9.toggle[0].label == TOG_KO)
    t9.toggle[0].set_value(False)
    t9.get("segmented_control")[0].set_value("zh")
    t9.run()
    check("꺼진 상태로 언어 전환: 꺼짐 유지", not t9.exception and t9.toggle[0].value is False and t9.toggle[0].label == TOG_ZH)

    t9b = new_app(ai=False)
    check("새 세션은 다시 기본 꺼짐(세션별 저장)", t9b.toggle[0].value is False)

    # 서버 미설정: 스위치 꺼짐 / 스위치만 켜고 키 없음 → 토글 비활성 + 캡션, 비밀값 노출 없음
    for label, cfg in [("설정 없음", {}), ("LLM_ENABLED 만 켜짐(키 없음)", {"LLM_ENABLED": "on"}),
                       ("키는 있으나 LLM_ENABLED 꺼짐", {"CLOUDFLARE_ACCOUNT_ID": "acc123", "CLOUDFLARE_API_TOKEN": "SECRET-TOKEN"})]:
        install(cfg)
        tu = new_app(ai=False)
        tg = tu.toggle[0] if tu.toggle else None
        text = all_text(tu)
        check(f"서버 미설정({label}): 토글 비활성·꺼짐", tg is not None and tg.disabled and tg.value is False, tg and (tg.disabled, tg.value))
        check(f"서버 미설정({label}): 안내 캡션(한국어)", "AI 기능이 서버에 설정되지 않았습니다" in text)
        check(f"서버 미설정({label}): 키·계정 값이 화면에 없음", "SECRET-TOKEN" not in text and "acc123" not in text)
        tu.chat_input[0].set_value(Q1).run()
        text = all_text(tu)
        check(f"서버 미설정({label}): 질문해도 기존 안내만, 호출 없음", not tu.exception and "죄송합니다" in text and LABEL_KO not in text and not CALLS)
    tu.get("segmented_control")[0].set_value("zh")
    tu.run()
    check("서버 미설정: 中文 캡션·라벨", not tu.exception and "服务器未配置AI功能" in all_text(tu) and tu.toggle[0].label == TOG_ZH and tu.toggle[0].disabled)

    # 서버 설정됨이지만 세션 토글 켠 뒤 서버 설정이 사라지면(재배포 등) 다시 꺼짐·비활성
    install(ON)
    tv = new_app(ai=True)
    check("[준비] 토글 켜짐", tv.toggle[0].value is True)
    install({})
    tv.run()
    check("서버 설정이 사라지면 토글은 꺼짐·비활성으로 돌아간다", not tv.exception and tv.toggle[0].value is False and tv.toggle[0].disabled)

    print("[10] 화면 문구가 키 이름(ai_toggle 등)이 아니라 i18n 문구로 나온다 (하단 고정 영역 st.bottom 포함)")
    import i18n as _i18n
    from i18n import STRINGS

    ALL_KEYS = set(STRINGS["ko"]) | set(STRINGS["zh"])
    check("[준비] ko/zh 문구 키가 같다·AI 토글 4개 키가 양쪽에 있다",
          set(STRINGS["ko"]) == set(STRINGS["zh"]) and {"ai_toggle", "ai_toggle_help", "ai_not_configured", "ai_on_notice"} <= ALL_KEYS)
    for cfg_name, cfg in [("서버 미설정(기본)", {}), ("서버 설정됨(가짜 값)", ON)]:
        for lg in ("ko", "zh"):
            S = STRINGS[lg]
            install(cfg)
            tl = new_app(ai=False)
            if lg == "zh":
                tl.get("segmented_control")[0].set_value("zh")
                tl.run()
            tg = tl.toggle[0] if tl.toggle else None
            caps = [c.value for c in tl.caption]
            tag = f"{cfg_name}/{lg}"
            check(f"{tag}: 토글 라벨 = i18n 문구(키 이름 아님)", tg is not None and tg.label == S["ai_toggle"] and tg.label != "ai_toggle", tg and tg.label)
            check(f"{tag}: 토글 도움말 = i18n 문구(키 이름 아님)", tg is not None and tg.help == S["ai_toggle_help"] and tg.help != "ai_toggle_help", tg and tg.help)
            if not cfg:
                check(f"{tag}: 미설정 캡션 = i18n 문구", S["ai_not_configured"] in caps and "ai_not_configured" not in caps, caps)
                check(f"{tag}: 토글 비활성", tg is not None and tg.disabled)
            else:
                check(f"{tag}: 미설정 캡션 없음·토글 사용 가능", S["ai_not_configured"] not in caps and tg is not None and not tg.disabled, caps)
                tl.toggle[0].set_value(True).run()
                caps = [c.value for c in tl.caption]
                check(f"{tag}: 켜면 안내 캡션 = i18n 문구", S["ai_on_notice"] in caps and "ai_on_notice" not in caps, caps)
            check(f"{tag}: 화면 어디에도(st.bottom 포함) 키 이름이 그대로 나오지 않는다", not raw_key_hits(tl, ALL_KEYS), raw_key_hits(tl, ALL_KEYS))
            check(f"{tag}: 하단 고정 영역에 토글·입력창이 같이 있다(트리 검사가 st.bottom 을 본다)",
                  any(len(b.toggle) == 1 and len(b.chat_input) == 1 for b in tl._tree.children.values()))

    # 대화가 진행된 화면에서도 키 이름이 새지 않는다
    install(ON)
    tc = new_app(ai=True)
    tc.chat_input[0].set_value(Q2).run()
    tc.chat_input[0].set_value("휴학 신청은 언제 해요?").run()
    tc.chat_input[0].set_value("더 자세히").run()
    tc.get("segmented_control")[0].set_value("zh")
    tc.run()
    check("대화 후·中文 전환 후에도 키 이름이 그대로 나오지 않는다", not tc.exception and not raw_key_hits(tc, ALL_KEYS), tc.exception or raw_key_hits(tc, ALL_KEYS))

    # 검사기가 실제로 잡아내는지(음성 대조): 키 이름이 새는 가짜 화면
    leak = AppTest.from_string("import streamlit as st\nst.caption('ai_not_configured')", default_timeout=60)
    leak.run()
    check("[대조] 키 이름이 새면 검사기가 잡아낸다", raw_key_hits(leak, ALL_KEYS) == ["ai_not_configured"], raw_key_hits(leak, ALL_KEYS))

    # 서버를 켜 둔 채 i18n.py 가 바뀐 상황(옛 사전이 메모리에 남음)을 흉내낸다. 실제 사고 원인.
    install({})
    ts = new_app(ai=False)
    check("[준비] 정상 상태", ts.toggle[0].label == STRINGS["ko"]["ai_toggle"] and hasattr(_i18n, "_loaded_mtime"))
    _good = {lg: dict(d) for lg, d in _i18n.STRINGS.items()}
    _old = {lg: {k: v for k, v in d.items() if not k.startswith("ai_")} for lg, d in _good.items()}  # AI 키가 없던 옛 사전
    _i18n.STRINGS.clear()
    _i18n.STRINGS.update(_old)
    _mt = _i18n._loaded_mtime
    ts2 = AppTest.from_file("app.py", default_timeout=60)
    ts2.run()  # 파일이 안 바뀌었으면(수정 시각 같음) 옛 사전 그대로 → 키 이름이 보여야 한다(재현)
    check("[재현] 옛 i18n 이 메모리에 남고 파일은 그대로면 키 이름이 보인다(검사기가 잡는다)",
          "ai_toggle" in raw_key_hits(ts2, ALL_KEYS) or any(x.label == "ai_toggle" for x in ts2.toggle),
          [x.label for x in ts2.toggle])
    _i18n._loaded_mtime = _mt - 100  # 파일이 서버 시작 뒤에 바뀐 것처럼
    ts3 = AppTest.from_file("app.py", default_timeout=60)
    ts3.run()
    S = _good["ko"]  # reload 로 _i18n.STRINGS 는 새 객체가 됐다(위의 STRINGS 는 옛 객체)
    check("[수정] i18n.py 가 바뀐 걸 감지해 다시 불러와 정상 문구가 나온다",
          not ts3.exception and ts3.toggle[0].label == S["ai_toggle"]
          # (다시 불러오면 llm_answer 의 가짜 _get 이 풀려 이 PC 의 실제 설정을 읽는다 → 미설정 캡션은 토글 비활성과 일치하기만 하면 된다)
          and (S["ai_not_configured"] in [c.value for c in ts3.caption]) == ts3.toggle[0].disabled
          and not raw_key_hits(ts3, ALL_KEYS) and "ai_toggle_help" in _i18n.STRINGS["ko"],
          ts3.exception or [x.label for x in ts3.toggle])
    print("[11] 사용자 보고 수정: 가드(무관한 짧은 질문)·오늘 날짜·URL 링크·中文 라벨 (AI 켜짐, HTTP 는 가짜)")
    LABEL_ZH_FULL = _i18n.STRINGS["zh"]["ai_label"]
    check("zh 라벨 전체 문구(未经确认)", LABEL_ZH_FULL == "🤖 AI自主回答，未经确认（FAQ中没有这个问题，由AI直接回答）")
    install(ON)
    a11 = new_app()
    a11.get("segmented_control")[0].set_value("zh")
    a11.run()
    a11.chat_input[0].set_value("你是什么模型").run()
    text = all_text(a11)
    check("'你是什么模型'(AI 켜짐): FAQ F23 에 붙지 않고 AI 답변(라벨 '未经确认', 출처·⚠️ 없음)",
          not a11.exception and len(CALLS) == 1 and LABEL_ZH_FULL in text and "默认确认" not in text and "F23" not in text and "依据：" not in text and "未验证" not in text,
          a11.exception or (len(CALLS), text[-300:]))
    sysmsg = PAYLOADS[0]["messages"][0]["content"] if PAYLOADS else ""
    d0 = la._today_kst()
    check("LLM 요청의 시스템 프롬프트에 오늘 날짜(Asia/Seoul)·모델명", f"{d0.year}年{d0.month}月{d0.day}日" in sysmsg and "具体模型名称为 @cf/google/gemma-4-26b-a4b-it" in sysmsg, sysmsg[:100])
    a11.chat_input[0].set_value("今天几号").run()
    check("'今天几号'(AI 켜짐): FAQ 에 붙지 않고 AI 로(호출 2번)", not a11.exception and len(CALLS) == 2 and "F23" not in all_text(a11), a11.exception or len(CALLS))

    # URL: 전각 부호·한자가 바로 붙어도 링크 주소는 URL 만(명시적 링크로 그린다)
    check("AI 안내 문구의 URL 이 명시적 링크로 그려진다(中文)", "[www.kyungnam.ac.kr](<https://www.kyungnam.ac.kr>)" in all_text(a11))
    install(ON)
    a12 = new_app()
    a12.get("segmented_control")[0].set_value("zh")
    a12.run()
    a12.chat_input[0].set_value("怎么登录学生信息系统").run()
    text = all_text(a12)
    check("FAQ 답변(F23): 选课网址 뒤 '，' 가 링크에 합쳐지지 않는다",
          "[https://sugang.kyungnam.ac.kr](<https://sugang.kyungnam.ac.kr>)，预选课" in text and "F23" in text and not CALLS, a12.exception or text[-300:])
    check("출처 줄의 URL 도 명시적 링크", "](<https://www.kyungnam.ac.kr/pdfView/international/49/fileDownload.do>)" in text)
    check("링크 주소(<...>) 안에 한자·전각 부호·xn-- 가 없다",
          not [h for h in re.findall(r"\]\(<([^>]*)>\)", text) if re.search(r"[^\x00-\x7f]", h) or "xn--" in h])
    MOCK_BAK = MOCK_TEXT
    MOCK_TEXT = "详见学校官网（www.kyungnam.ac.kr），或 https://www.hikorea.go.kr）谢谢"
    install(ON)
    a13 = new_app()
    a13.chat_input[0].set_value("한국에서 은행 계좌 만드는 방법 알려줘").run()
    text = all_text(a13)
    MOCK_TEXT = MOCK_BAK
    check("AI 답변 속 URL: 뒤에 붙은 전각 괄호·쉼표·한자와 분리된 링크",
          "（[www.kyungnam.ac.kr](<https://www.kyungnam.ac.kr>)），或" in text
          and "[https://www.hikorea.go.kr](<https://www.hikorea.go.kr>)）谢谢" in text, a13.exception or text[-400:])
finally:
    la._get, la._http_post, la.LOG_PATH = _saved
    la.reset_state()
    shutil.rmtree(_tmp, ignore_errors=True)

print()
if FAILS:
    print(f"실패 {len(FAILS)}건: {FAILS}")
    sys.exit(1)
print("모두 통과")
