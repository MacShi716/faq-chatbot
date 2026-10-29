# -*- coding: utf-8 -*-
"""대화 보조 규칙: 인사·감사·도움말·후속 요청을 가려낸다.

FAQ 답변은 그대로 검색 결과만 쓰고, 여기서는 '말투'와 '맥락'만 다룬다(답을 지어내지 않는다).
의도는 정규화한 전체 문장이 아래 목록과 정확히 같을 때만 인정한다.
(예: "다시 학교 다니려면" 같은 실제 질문이 "다시" 때문에 잘못 걸리지 않도록)
"""

from __future__ import annotations

import difflib
import re

from llm_answer import free_answer
from normalize import detect_lang, normalize
from retriever import DEFAULT_THRESHOLD, is_filled

# "혹시 이런 질문인가요?" 후보로 보여줄 최소 유사도(너무 동떨어진 후보는 숨긴다).
SUGGEST_MIN_SCORE = 0.2

# --- '약한 매칭' 가드 (AI 대화 토글과 상관없이 항상 적용) -------------------------------------------------------
# 문제: difflib 는 "你是什么模型" 과 "学正时是什么？" 처럼 '是什么' 같은 흔한 의문 표현만 겹쳐도 0.5 가 나온다.
#       임계값(0.4)만 넘으면 학교와 무관한 질문("학교 수영장 몇 시까지 해요?" → 휴학)에도 FAQ 답이 붙는다.
# 해결: 유사도가 STRONG_SCORE 이상(태그 적중은 항상 0.7 이상)이면 그대로 믿고,
#       그보다 약하면 '흔한 의문 표현을 뺀 알맹이'끼리의 유사도(content_score)가 MIN_CONTENT_SCORE 이상일 때만 믿는다.
#       믿을 수 없는 매칭은 AI 꺼짐이면 '답 없음(학과 사무실 문의)' + 걸러진 제안, AI 켜짐이면 Tier B 로 간다.
# MIN_CONTENT_SCORE: 0.40 이면 "你会说韩语吗"(알맹이 '说韩语' vs F21 태그 '韩语等级' = 0.57)가 통과했다.
#       평가셋과 FAQ 표현 빼고 넣기(leave-one-out) 점검에서 0.4~0.65 구간의 맞는 매칭은 모두 0.60 이상이었다.
STRONG_SCORE = 0.65
MIN_CONTENT_SCORE = 0.60

_GENERIC_WORDS = (
    # 中文 의문·조동 표현
    "什么时候", "是什么", "怎么办", "怎么样", "怎么", "什么", "如何", "可以", "能不能", "请问", "一下", "多少", "哪里", "在哪",
    "吗", "呢", "吧", "啊", "的", "是", "有", "要", "你", "我", "想", "能", "会", "还", "了", "这", "那", "个",
    # 한국어 의문·어미
    "어떻게", "언제", "뭐예요", "뭐에요", "무엇", "어디", "얼마", "해요", "하나요", "있나요", "인가요", "알려주세요", "알려줘",
    "가능한가요", "되나요", "돼요", "요", "까", "나", "가", "은", "는", "이", "를", "을", "에", "도", "좀", "몇",
)
_GENERIC_RE = re.compile("|".join(re.escape(w) for w in sorted({normalize(w) for w in _GENERIC_WORDS}, key=len, reverse=True)))


def _core(text: str) -> str:
    """정규화한 뒤 흔한 의문 표현을 뺀 알맹이."""
    return _GENERIC_RE.sub("", normalize(text))


def content_score(query: str, faq, lang: str) -> float:
    """흔한 의문 표현을 뺀 질문과 FAQ 질문·키워드 사이의 가장 높은 difflib 유사도(0~1)."""
    q = _core(query)
    if not q:
        return 0.0
    best = 0.0
    for term in faq.search_terms(lang):
        t = _core(term)
        if t:
            best = max(best, difflib.SequenceMatcher(None, q, t).ratio())
    return best


def is_confident_match(query: str, match, lang: str) -> bool:
    """이 FAQ 매칭을 믿어도 되는가(흔한 의문 표현만 겹친 약한 우연 일치가 아닌가)."""
    return match.score >= STRONG_SCORE or content_score(query, match.faq, lang) >= MIN_CONTENT_SCORE


def is_answerable(faq) -> bool:
    """답으로 보여줄 수 있는 FAQ 인가. 미작성 초안([작성 필요]/[待填写]·빈 답변)은 답·제안·관련 질문에서 뺀다."""
    return is_filled(faq.answer)


def pick_match(query: str, top: list, lang: str, threshold: float = DEFAULT_THRESHOLD):
    """검색 결과(top, 유사도 순)에서 답으로 보여줄 매칭. 없으면 None(= 답 없음 / Tier B).

    1위가 임계값 미달·미작성 초안·약한 우연 일치면 None 이다(2위로 내려가지 않는다: 엉뚱한 답보다 '답 없음'이 낫다).
    화면(build_entry)과 evaluate.py 가 같은 판단을 쓴다.
    """
    if not top:
        return None
    best = top[0]
    if best.score < threshold or not is_answerable(best.faq) or not is_confident_match(query, best, lang):
        return None
    return best


def suggestions_for(query: str, top: list, lang: str) -> list:
    """'혹시 이런 질문인가요?' 제안. 미작성 초안과 약한 우연 일치는 뺀다."""
    return [c.faq for c in top
            if c.score >= SUGGEST_MIN_SCORE and is_answerable(c.faq) and is_confident_match(query, c, lang)]


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
        if cand.faq.id != matched_faq.id and cand.score >= min_score and is_answerable(cand.faq):
            out.append(cand.faq)
        if len(out) >= limit:
            break
    return out

def _talk(key: str) -> dict:
    return {"role": "assistant", "kind": "talk", "key": key}


def build_entry(prompt: str, history: list[dict], index, session_key: str = "default", ai_enabled: bool = False) -> dict:
    """질문 한 건에 대한 답변 기록(dict)을 만든다. 화면 그리기는 app.py 가 맡는다.

    Tier A: FAQ 매칭(pick_match: 임계값·약한 매칭 가드·미작성 제외) → kind "match" (FAQ 답변 그대로, 출처·확인일).
    Tier B: 매칭 실패 + ai_enabled(사용자가 화면 토글을 켬) + 서버 LLM_ENABLED → kind "ai" (AI 자율 답변, 출처 없음).
    ai_enabled 가 False(기본)이거나 서버가 꺼져 있거나 실패하면 kind "none"(학과 사무실 문의 안내 + 제안).
    """
    intent = detect_intent(prompt)
    if intent in ("greet", "thanks", "bye", "help"):
        return _talk(f"talk_{intent}")

    if intent in ("followup", "to_zh", "to_ko"):
        last = next((e for e in reversed(history) if e.get("kind") in ("match", "ai")), None)
        if last is None:
            return _talk("talk_no_context")
        if last.get("kind") == "ai":  # AI 답변은 다시 보여주기·번역을 지원하지 않는다
            return _talk("talk_ai_followup")
        forced = {"to_zh": "zh", "to_ko": "ko"}.get(intent, last.get("force_lang"))
        return {**last, "lead": "followup_note" if intent == "followup" else None, "force_lang": forced}

    lang = detect_lang(prompt)
    top = index.search(prompt, lang=lang, top_k=3)
    candidates = [(c.score, c.faq.id, c.faq.question_ko) for c in top]
    # 약한 우연 일치(흔한 의문 표현만 겹침)·미작성 초안은 AI 토글과 상관없이 '매칭 없음'으로 본다.
    match = pick_match(prompt, top, lang, index.threshold)
    if match is None:
        best = top[0].score if top else None
        none_entry = {
            "role": "assistant",
            "kind": "none",
            "best": best,
            "suggestions": suggestions_for(prompt, top, lang),
            "candidates": candidates,
        }
        try:  # Tier B (사용자가 안 켰거나 서버가 꺼져 있으면 None → 답 없음 안내)
            ai = free_answer(prompt, lang, best=best, key=session_key, ai_enabled=ai_enabled)
        except Exception:  # noqa: BLE001 - LLM 쪽 문제로 대화가 끊기면 안 된다
            ai = {"kind": "unavailable"}
        if ai is None:
            return none_entry
        if ai.get("kind") == "ai":
            # 답변 문장을 기록에 저장해 두므로 화면이 다시 그려져도 LLM 을 다시 부르지 않는다.
            return {**none_entry, "kind": "ai", "text": ai["text"], "model": ai.get("model", "")}
        if ai.get("kind") == "template":
            return {**none_entry, "template": True}
        return {**none_entry, "ai_failed": True}
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
