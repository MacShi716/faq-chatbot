# -*- coding: utf-8 -*-
"""대화 보조 규칙: 인사·감사·도움말·후속 요청을 가려낸다.

FAQ 답변은 그대로 검색 결과만 쓰고, 여기서는 '말투'와 '맥락'만 다룬다(답을 지어내지 않는다).
의도는 정규화한 전체 문장이 아래 목록과 정확히 같을 때만 인정한다.
(예: "다시 학교 다니려면" 같은 실제 질문이 "다시" 때문에 잘못 걸리지 않도록)
"""

from __future__ import annotations

from normalize import detect_lang, normalize

# "혹시 이런 질문인가요?" 후보로 보여줄 최소 유사도(너무 동떨어진 후보는 숨긴다).
SUGGEST_MIN_SCORE = 0.2

_INTENTS: dict[str, set[str]] = {
    "greet": {
        "안녕", "안녕하세요", "안녕하십니까", "하이", "헬로", "hi", "hello", "hey",
        "你好", "您好", "嗨", "哈喽", "哈啰", "早上好", "晚上好",
    },
    "thanks": {
        "고마워", "고마워요", "고맙습니다", "감사", "감사합니다", "감사해요", "땡큐", "thanks", "thankyou",
        "谢谢", "谢谢你", "多谢", "感谢", "谢啦",
    },
    "bye": {
        "잘가", "안녕히계세요", "안녕히가세요", "바이", "bye", "byebye", "拜拜", "再见", "下次见",
    },
    "help": {
        "도움말", "도움", "뭐할수있어", "뭐할수있어요", "뭘도와줄수있어", "사용법", "어떻게써", "help",
        "帮助", "你能做什么", "你会什么", "怎么用", "使用方法",
    },
    "followup": {
        "다시", "한번더", "더", "더알려줘", "더알려주세요", "더자세히", "자세히", "자세히알려줘",
        "자세히알려주세요", "다시알려줘", "다시말해줘",
        "详细一点", "详细点", "再详细点", "再详细一点", "详细说说", "再说一次", "再说一遍", "还有吗",
    },
    "to_zh": {
        "중국어로", "중국어로알려줘", "중국어로말해줘", "用中文", "用中文说", "用中文回答", "说中文", "中文回答",
    },
    "to_ko": {
        "한국어로", "한국어로알려줘", "한국어로말해줘", "用韩语", "用韩文", "用韩语说", "韩语原文",
    },
}

_LOOKUP = {phrase: intent for intent, phrases in _INTENTS.items() for phrase in (normalize(p) for p in phrases)}


def detect_intent(text: str) -> str | None:
    """greet / thanks / bye / help / followup / to_zh / to_ko 중 하나, 아니면 None(= 일반 질문)."""
    return _LOOKUP.get(normalize(text))


def related_faqs(candidates, matched_faq, min_score: float = 0.3, limit: int = 2) -> list:
    """방금 답한 FAQ 말고, 이어서 물어볼 만한 FAQ(유사도 min_score 이상)를 최대 limit 개."""
    out = []
    for cand in candidates:
        if cand.faq.id != matched_faq.id and cand.score >= min_score:
            out.append(cand.faq)
        if len(out) >= limit:
            break
    return out

def _talk(key: str) -> dict:
    return {"role": "assistant", "kind": "talk", "key": key}


def build_entry(prompt: str, history: list[dict], index) -> dict:
    """질문 한 건에 대한 답변 기록(dict)을 만든다. 화면 그리기는 app.py 가 맡는다."""
    intent = detect_intent(prompt)
    if intent in ("greet", "thanks", "bye", "help"):
        return _talk(f"talk_{intent}")

    if intent in ("followup", "to_zh", "to_ko"):
        last = next((e for e in reversed(history) if e.get("kind") == "match"), None)
        if last is None:
            return _talk("talk_no_context")
        forced = {"to_zh": "zh", "to_ko": "ko"}.get(intent, last.get("force_lang"))
        return {**last, "lead": "followup_note" if intent == "followup" else None, "force_lang": forced}

    lang = detect_lang(prompt)
    top = index.search(prompt, lang=lang, top_k=3)
    candidates = [(c.score, c.faq.id, c.faq.question_ko) for c in top]
    match = index.answer(prompt, lang=lang)
    if match is None:
        return {
            "role": "assistant",
            "kind": "none",
            "best": top[0].score if top else None,
            "suggestions": [c.faq for c in top if c.score >= SUGGEST_MIN_SCORE],
            "candidates": candidates,
        }
    return {
        "role": "assistant",
        "kind": "match",
        "faq": match.faq,
        "score": match.score,
        "method": match.method,
        "lead": "lead_found",
        "related": related_faqs(top, match.faq),
        "candidates": candidates,
    }
