# -*- coding: utf-8 -*-
"""학과 교무·생활 Q&A 챗봇 - Streamlit 화면.

실행:  streamlit run app.py
"""

import importlib
import os
import time
import uuid
from pathlib import Path

import streamlit as st

import chat_logic
import i18n
import linkify
import llm_answer
import normalize
import retriever

# 서버를 켜 둔 채 .py 파일이 바뀌면, 이미 import 된 모듈(i18n 등)은 옛 내용 그대로 메모리에 남을 수 있다.
# 그러면 새 app.py 가 새 문구 키(예: ai_toggle)를 불러도 옛 사전에는 없어서 키 이름이 그대로 화면에 나온다.
# 스크립트가 다시 실행될 때마다 파일 수정 시각을 확인해, 바뀐 모듈이 있으면 의존 순서대로 다시 불러온다.
_LOCAL_MODULES = (normalize, linkify, retriever, i18n, llm_answer, chat_logic)  # 의존 순서(앞이 뒤에서 쓰인다)


def _reload_stale_local_modules() -> bool:
    changed = False
    for mod in _LOCAL_MODULES:
        mtime = os.path.getmtime(mod.__file__)
        seen = getattr(mod, "_loaded_mtime", None)
        if seen is None:  # 방금 import 됐거나 처음 확인하는 모듈: 지금 파일 시각을 기준으로 삼는다
            mod._loaded_mtime = mtime
        elif mtime > seen:
            changed = True
    if changed:
        for mod in _LOCAL_MODULES:
            importlib.reload(mod)
            mod._loaded_mtime = os.path.getmtime(mod.__file__)
        st.cache_resource.clear()  # 옛 Retriever 객체가 남지 않게 한다
    return changed


_reload_stale_local_modules()

from chat_logic import build_entry
from i18n import LANG_LABELS, LANGS, get_lang, t
from linkify import escape_markdown, safe_links, safe_markdown
from llm_answer import is_available
from retriever import DEFAULT_FAQ_PATH, DEFAULT_THRESHOLD, Retriever, is_filled, load_faqs

st.set_page_config(
    page_title="학과 Q&A 챗봇 · 院系问答机器人",
    page_icon="💬",
    layout="centered",
)

STYLE_PATH = Path(__file__).with_name("styles.css")
st.html(f"<style>{STYLE_PATH.read_text(encoding='utf-8')}</style>")

# 브라우저(Chrome·Edge)의 자동 번역이 화면 문구를 바꿔 버리지 않게 한다(예: "未经确认" → "默认确认").
# 이 앱은 한국어/中文 화면을 직접 제공하므로 번역이 필요 없다. 높이 0 짜리 조각에서 상위 문서에 표시를 단다.
_NOTRANSLATE_HTML = (
    "<script>try{var d=window.parent.document;d.documentElement.setAttribute('translate','no');"
    "d.documentElement.classList.add('notranslate');"
    "if(!d.querySelector('meta[name=google]')){var m=d.createElement('meta');m.name='google';m.content='notranslate';d.head.appendChild(m);}"
    "}catch(e){}</script>"
)
try:
    if hasattr(st, "iframe"):  # 최신 Streamlit: components.v1.html 은 곧 없어진다는 경고가 있어 st.iframe 을 쓴다
        st.iframe(_NOTRANSLATE_HTML, height=1)
    else:
        import streamlit.components.v1 as components

        components.html(_NOTRANSLATE_HTML, height=0)
except Exception:  # noqa: BLE001 - 번역 방지는 있으면 좋은 보조 기능이다. 실패해도 앱은 그대로 동작해야 한다
    pass

# 화면에는 프로젝트 기준 상대 경로만 보여준다(전체 경로가 노출되지 않도록).
REL_FAQ_PATH = "data/faq.csv"
FAQ_DIR = DEFAULT_FAQ_PATH.parent.parent

# 처음 화면에 보여주는 예시 질문(눌러서 바로 질문). 화면 언어에 맞춰 한 가지 언어로만 보여준다.
EXAMPLE_QUESTIONS = {
    "ko": ["휴학 신청은 언제 해요?", "수강신청은 언제 해요?", "비자 연장은 어떻게 해요?"],
    "zh": ["什么时候可以申请休学？", "什么时候选课？", "签证续签要多久"],
}


def resolve_faq_path(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else FAQ_DIR / p


@st.cache_resource(show_spinner=False)
def get_retriever(faq_path: str, method: str, threshold: float) -> Retriever:
    return Retriever(faqs=load_faqs(resolve_faq_path(faq_path)), threshold=threshold, method=method)


def render_source(faq, score: float, method: str) -> None:
    # 출처·확인일은 데이터라 safe_markdown(링크 + 마크다운 특수 문자 이스케이프)을 거쳐 문구 틀에 넣는다.
    # (URL 이 뒤따르는 전각 부호·한자와 한 링크로 합쳐지지 않고, '~' 가 취소선이 되지 않게 한다)
    st.caption(
        t(
            "source",
            source=safe_markdown(faq.source) if faq.source else t("source_unknown"),
            checked=safe_markdown(faq.checked_at) if faq.checked_at else t("checked_unknown"),
            id=faq.id,
            score=score,
            method=method,
        )
    )


def render_candidates(candidates) -> None:
    with st.expander(t("candidates")):
        for score, faq_id, question in candidates:
            st.write(f"{score:.3f} · {faq_id} · {escape_markdown(question)}")


def typewriter(text: str):
    """답변을 조금씩 보여주는 효과(전체 약 0.5초 안팎). 링크는 한 번에 보여 마크다운 원문이 비치지 않게 한다."""
    delay = min(0.012, 1.0 / max(len(text), 1))
    for chunk in linkify.typing_chunks(text):
        yield chunk
        time.sleep(delay)


def say(text: str, stream: bool, mode: str = "ui") -> None:
    """mode: "data"(FAQ 답변) / "ai"(AI 답변) / "ui"(화면 문구). linkify.safe_markdown 참고.

    답변 속 URL 바로 뒤에 "，" "）" 같은 전각 부호·한자가 붙어도 링크가 깨지지 않게 하고,
    '9/1~9/28' 의 '~' 가 취소선, '$' 가 수식으로 그려지지 않게 이스케이프한다(타자 효과는 '\\~' 를 쪼개지 않는다).
    """
    text = safe_markdown(text, mode)
    if stream and text:
        st.write_stream(typewriter(text))
    else:
        st.markdown(text)


def question_button(idx: int, faq, prefix: str) -> None:
    text = (faq.variants(get_lang()) or faq.variants("ko"))[0] or faq.question_ko
    # 버튼 라벨도 마크다운으로 그려진다: 라벨만 이스케이프하고, 눌렀을 때 보내는 질문은 원문 그대로
    if st.button(escape_markdown(text), key=f"{prefix}_{idx}_{faq.id}"):
        st.session_state.pending_prompt = text


def render_match(idx: int, entry: dict, stream: bool) -> None:
    faq = entry["faq"]
    reply, fell_back = faq.answer_for(entry.get("force_lang") or get_lang())
    if entry.get("lead"):
        st.markdown(t(entry["lead"]))
    if not is_filled(reply) or not faq.checked_at:
        st.markdown(f":orange-badge[{t('unverified')}]")
    say(reply, stream, "data")
    if fell_back:
        st.caption(t("ko_original"))
    render_source(faq, entry["score"], entry["method"])
    if entry.get("related"):
        st.caption(t("related_label"))
        for rel in entry["related"]:
            question_button(idx, rel, "rel")


def render_suggestions(idx: int, entry: dict) -> None:
    if entry["suggestions"]:
        st.caption(t("suggest_label"))
        for faq in entry["suggestions"]:
            question_button(idx, faq, "sug")


def render_none(idx: int, entry: dict, stream: bool) -> None:
    if entry.get("template"):  # 학교 고유 정보(전화·비용·일정·장소): LLM 을 부르지 않고 고정 안내
        say(t("school_fact_template"), stream)
    else:
        shown = chat_logic.shown_best(entry)  # 화면에 제안한 후보 기준(숨긴 미작성 초안의 점수는 보여 주지 않는다)
        best = t("best_candidate", score=shown) if shown is not None else ""
        say(t("no_answer", best=best), stream)
        if entry.get("ai_failed"):  # AI 답변이 켜져 있는데 가져오지 못한 경우
            st.caption(t("ai_unavailable"))
    render_suggestions(idx, entry)


def render_ai(idx: int, entry: dict, stream: bool) -> None:
    """Tier B: FAQ 에 없는 질문에 대한 AI 자율 답변. 항상 라벨이 먼저, 출처 줄(render_source)은 절대 없다."""
    st.markdown(f":orange-badge[{t('ai_label')}]")
    say(entry["text"], stream, "ai")
    st.caption(safe_links(t("ai_nudge")))
    if entry.get("model"):
        st.caption(t("ai_model", model=entry["model"]))
    render_suggestions(idx, entry)


def render_entry(idx: int, entry: dict, show_debug: bool, stream: bool = False) -> None:
    """대화 기록 한 건을 현재 화면 언어로 다시 그린다(언어·검색방식을 바꿔도 출처 줄이 유지된다)."""
    with st.chat_message(entry["role"]):
        kind = entry.get("kind")
        if kind is None:  # 사용자 말풍선
            st.markdown(safe_markdown(entry["text"]))  # 사용자가 쓴 글: 링크 + 마크다운 특수 문자 이스케이프
        elif kind == "talk":
            say(t(entry["key"]), stream)
        else:
            {"match": render_match, "ai": render_ai}.get(kind, render_none)(idx, entry, stream)
            if show_debug and entry.get("candidates"):
                render_candidates(entry["candidates"])


# --- 화면 언어 전환: 오른쪽 위, 작은 세그먼트 버튼 -------------------------------
def on_lang_change() -> None:
    """선택된 항목을 다시 눌러도 선택이 해제되지 않게 한다(해제되면 버튼이 눌리지 않는 것처럼 보인다)."""
    picked = st.session_state.ui_lang_picker
    if picked:
        st.session_state.ui_lang = picked
    else:
        st.session_state.ui_lang_picker = get_lang()


def on_ai_toggle() -> None:
    """AI 대화 토글: 세션별 선택을 ai_on 에 저장한다. 켜는 순간에만 안내(toast)를 한 번 띄운다."""
    on = bool(st.session_state.ai_toggle)
    st.session_state.ai_on = on
    if on:
        st.session_state.ai_notice_pending = True


st.session_state.setdefault("ui_lang_picker", get_lang())
_, lang_col = st.columns([1, 0.34])
with lang_col:
    st.segmented_control(
        t("lang_label"),
        options=list(LANGS),
        format_func=lambda code: LANG_LABELS[code],
        label_visibility="collapsed",
        key="ui_lang_picker",
        on_change=on_lang_change,
    )
lang = get_lang()

if "history" not in st.session_state:
    st.session_state.history = []

with st.sidebar:
    st.header(t("settings"))
    method = st.radio(
        t("search_method"),
        options=["difflib", "tfidf"],
        index=0,
        captions=[t("method_difflib"), t("method_tfidf")],
    )
    show_debug = st.checkbox(t("show_candidates"), value=False)
    with st.expander(t("advanced")):
        faq_path = st.text_input(t("faq_file"), value=REL_FAQ_PATH)
        threshold = st.slider(t("threshold"), 0.1, 0.9, DEFAULT_THRESHOLD, 0.05)

    try:
        index = get_retriever(faq_path, method, threshold)
        st.success(t("loaded", n=len(index.faqs)))
    except Exception as exc:  # 데이터 오류를 화면에서 바로 확인하기 위함
        st.error(t("load_error", err=exc))
        st.stop()

    if st.button(t("clear"), use_container_width=True):
        st.session_state.history = []
        st.session_state.pop("pending_prompt", None)

st.title(t("title"))
st.markdown(
    '<div class="chips">' + "".join(f'<span class="chip">{c}</span>' for c in t("chips").split("|")) + "</div>",
    unsafe_allow_html=True,
)
# AI 대화 토글: 채팅 입력창(st.chat_input) 바로 위에 붙여, 입력창과 항상 함께 보이게 한다(하단 고정 영역).
# 서버에 AI 설정이 있어야(is_available) 쓸 수 있고, 켜는 것은 사용자(세션)별 선택이다. 기본은 꺼짐.
ai_available = is_available()
st.session_state.setdefault("ai_on", False)
if not ai_available:
    st.session_state.ai_on = False
st.session_state.ai_toggle = st.session_state.ai_on  # 화면 언어가 바뀌어 위젯이 새로 만들어져도 상태 유지
# st.chat_input 은 최상위에서 호출하면 화면 맨 아래 영역(st.bottom)에 고정된다. 같은 영역에 토글을 먼저 그리면
# 토글이 입력창 바로 위에 놓인다. st.bottom 이 없는 옛 버전은 st._bottom, 그것도 없으면 일반 컨테이너로 대신한다.
bottom_zone = getattr(st, "bottom", None) or getattr(st, "_bottom", None) or st.container()
with bottom_zone:
    st.toggle(
        t("ai_toggle"),
        key="ai_toggle",
        help=t("ai_toggle_help"),
        disabled=not ai_available,
        on_change=on_ai_toggle,
    )
    ai_enabled = ai_available and bool(st.session_state.ai_on)
    if not ai_available:  # 안내 문구는 토글 바로 아래에 작게(styles.css 의 하단 영역 규칙)
        st.caption(t("ai_not_configured"))
    elif ai_enabled:
        st.caption(t("ai_on_notice"))
if ai_enabled and st.session_state.pop("ai_notice_pending", False):
    st.toast(t("ai_on_notice"), icon="🤖", duration="long")
st.caption(t("disclaimer"))

typed = st.chat_input(t("chat_input"))

# 대화가 비어 있으면 예시 질문 버튼을 보여준다(질문이 들어오면 바로 숨긴다).
examples_box = st.empty()
if not st.session_state.history and "pending_prompt" not in st.session_state:
    with examples_box.container():
        with st.chat_message("assistant"):
            st.markdown(t("welcome"))
        st.caption(t("examples_label"))
        examples = EXAMPLE_QUESTIONS[get_lang()]
        cols = st.columns(len(examples))
        for col, question in zip(cols, examples):
            if col.button(question, key=f"ex_{question}", use_container_width=True):
                st.session_state.pending_prompt = question

for i, entry in enumerate(st.session_state.history):
    render_entry(i, entry, show_debug)

prompt = st.session_state.pop("pending_prompt", None) or typed
if prompt:
    examples_box.empty()
    st.session_state.history.append({"role": "user", "text": prompt})
    with st.chat_message("user"):
        st.markdown(safe_markdown(prompt))

    st.session_state.setdefault("session_id", uuid.uuid4().hex)  # AI 답변 속도 제한 단위
    entry = build_entry(
        prompt, st.session_state.history, index, session_key=st.session_state.session_id, ai_enabled=ai_enabled
    )
    st.session_state.history.append(entry)
    render_entry(len(st.session_state.history) - 1, entry, show_debug, stream=True)

st.divider()
st.caption(t("footer"))