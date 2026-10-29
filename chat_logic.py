# -*- coding: utf-8 -*-
"""대화 보조 규칙: 인사·감사·도움말·후속 요청을 가려낸다.

FAQ 답변은 그대로 검색 결과만 쓰고, 여기서는 '말투'와 '맥락'만 다룬다(답을 지어내지 않는다).
의도는 정규화한 전체 문장이 아래 목록과 정확히 같을 때만 인정한다.
(예: "다시 학교 다니려면" 같은 실제 질문이 "다시" 때문에 잘못 걸리지 않도록)
"""

from __future__ import annotations

import re

from llm_answer import free_answer
from normalize import detect_lang, normalize
from retriever import DEFAULT_THRESHOLD, _GENERIC_RE, _GENERIC_WORDS, _core, content_score, is_filled  # noqa: F401 (다른 모듈·테스트가 여기서 가져다 쓴다)

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
# (알맹이 유사도 content_score 와 흔한 의문 표현 목록은 검색 순위에도 쓰이므로 retriever.py 에 있다)

# --- '애매한 1위' 가드 (QA AC-1 2차, 2026-10-29) -------------------------------------------------------------------
# 문제: "외국인등록증 갱신 어떻게 해요" 는 F15(발급)·F30·F16(주소 변경)이 거의 같은 점수로 겹치는데,
#       어느 FAQ 에도 '갱신' 이 없다. 이럴 때 1위를 그대로 보여 주면 엉뚱한 답이 나온다.
# 해결: 1위와 2위의 순위 점수(문자열 + 알맹이 유사도) 차가 AMBIGUOUS_MARGIN 미만으로 '박빙'이고,
#       1위 FAQ 의 질문·표현·태그에 질문의 핵심 낱말이 하나라도 빠져 있으면 답하지 않는다(답 없음 + 후보 제안 / AI 켜짐이면 Tier B).
#       박빙이어도 핵심 낱말이 모두 들어 있으면(예: "复学申请流程" → F02 vs F38, "毕业条件是什么" → F03 vs F21) 1위를 믿는다.
#       핵심 낱말만 빠진 경우(박빙 아님)도 믿는다: "수강신청 날짜", "休学需要提交什么材料" 처럼 부수 낱말이 FAQ 에 없는 맞는 매칭이 많다.
#       FAQ 표현과 글자까지 똑같은 질문(유사도 1.0)은 박빙이어도 바로 답한다.
# AMBIGUOUS_MARGIN 0.10: 내부 평가셋에서 맞는 매칭 중 '박빙 + 낱말 빠짐'은 없었고, 가장 가까운 맞는 매칭은 0.14(K06) 차이였다.
AMBIGUOUS_MARGIN = 0.10

# 핵심 낱말을 뽑을 때 떼어 내는 한국어 조사·어미(띄어쓰기 단위 끝에서만 뗀다)와, 핵심 낱말로 보지 않는 말.
_KO_ENDINGS = tuple(sorted({
    "으려면", "하려면", "려면", "이에요", "예요", "에요", "인가요", "하나요", "해요", "해야", "하고", "하는", "하면", "싶어요", "싶어",
    "있어요", "있어", "나요", "가요", "까지", "에서", "으로", "로", "요", "은", "는", "이", "가", "을", "를", "에", "도", "의", "랑", "면",
}, key=len, reverse=True))
_NOT_KEY = {normalize(w) for w in _GENERIC_WORDS} | {"얼마나", "어디서", "어디에", "뭐", "무슨"}
_HANGUL_RE = re.compile(r"[\uac00-\ud7a3]")


def _strip_ko(token: str) -> str:
    """한국어 띄어쓰기 단위 끝의 조사·어미를 뗀다(가운데 글자는 건드리지 않는다). 남는 게 흔한 말이면 ''."""
    while token and token not in _NOT_KEY and token not in _KO_ENDINGS:
        cut = next((e for e in _KO_ENDINGS if token.endswith(e) and len(token) > len(e)), None)
        if cut is None:
            break
        token = token[: -len(cut)]
    return "" if token in _NOT_KEY or token in _KO_ENDINGS else token


def key_words(query: str, lang: str) -> list[str]:
    """질문의 핵심 낱말(2글자 이상).

    한국어: 띄어쓰기 단위마다 끝의 조사·어미를 뗀 것 (예: "기준이" → "기준", "들어가려면" → "들어").
    중국어(띄어쓰기 없음): 흔한 의문 표현을 경계로 나눈 조각 (예: "什么时候可以复学" → "复学").
    """
    out = []
    for token in (query or "").split():
        t = normalize(token)
        chunks = [_strip_ko(t)] if _HANGUL_RE.search(t) else _GENERIC_RE.split(t)
        out += [c for c in chunks if len(c) >= 2]
    return out


def missing_key_words(query: str, faq, lang: str) -> list[str]:
    """FAQ 질문·표현·태그 어디에도 나오지 않는 핵심 낱말. 낱말의 2글자 조각 하나라도 나오면 들어 있는 것으로 본다."""
    text = "|".join(normalize(t) for t in faq.search_terms(lang))
    return [w for w in key_words(query, lang) if not any(w[i:i + 2] in text for i in range(len(w) - 1))]


def is_ambiguous(query: str, top: list, lang: str) -> bool:
    """1위가 2위와 박빙(순위 점수 차 < AMBIGUOUS_MARGIN)인데 1위 FAQ 에 질문 핵심 낱말이 빠져 있는가."""
    if len(top) < 2 or top[0].score >= 1.0:
        return False
    close = top[0].rank_score - top[1].rank_score < AMBIGUOUS_MARGIN
    return close and bool(missing_key_words(query, top[0].faq, lang))


def is_confident_match(query: str, match, lang: str) -> bool:
    """이 FAQ 매칭을 믿어도 되는가(흔한 의문 표현만 겹친 약한 우연 일치가 아닌가)."""
    return match.score >= STRONG_SCORE or content_score(query, match.faq, lang) >= MIN_CONTENT_SCORE


def is_answerable(faq) -> bool:
    """답으로 보여줄 수 있는 FAQ 인가. 미작성 초안([작성 필요]/[待填写]·빈 답변)은 답·제안·관련 질문에서 뺀다."""
    return is_filled(faq.answer)


def pick_match(query: str, top: list, lang: str, threshold: float = DEFAULT_THRESHOLD):
    """검색 결과(top, 유사도 순)에서 답으로 보여줄 매칭. 없으면 None(= 답 없음 / Tier B).

    1위가 임계값 미달·미작성 초안·약한 우연 일치·애매한 1위(is_ambiguous)면 None 이다
    (2위로 내려가지 않는다: 엉뚱한 답보다 '답 없음'이 낫다). top 은 2위까지 있어야 박빙 여부를 볼 수 있다(top_k=3 권장).
    화면(build_entry)과 evaluate.py 가 같은 판단을 쓴다.
    """
    if not top:
        return None
    best = top[0]
    if best.score < threshold or not is_answerable(best.faq) or not is_confident_match(query, best, lang):
        return None
    if is_ambiguous(query, top, lang):
        return None
    return best


def suggestions_for(query: str, top: list, lang: str) -> list:
    """'혹시 이런 질문인가요?' 제안. 미작성 초안과 약한 우연 일치는 뺀다."""
    return [c.faq for c in top
            if c.score >= SUGGEST_MIN_SCORE and is_answerable(c.faq) and is_confident_match(query, c, lang)]


def shown_best(entry: dict) -> float | None:
    """'답 없음' 안내의 '가장 유사한 후보 유사도' 로 보여 줄 값.

    화면에 실제로 제안한 후보(suggestions) 중 가장 높은 유사도. 제안이 없으면 None(그 줄을 숨긴다).
    예전에는 검색 1위 점수를 그대로 써서, 숨긴 미작성 초안(F10 등)에 자기 질문이 1.00 으로 맞으면
    '가장 유사한 후보 유사도 1.00' 이라는 오해를 부르는 문구가 나왔다.
    """
    ids = {f.id for f in entry.get("suggestions") or []}
    scores = [score for score, fid, _ in entry.get("candidates") or [] if fid in ids]
    return max(scores) if scores else None


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
