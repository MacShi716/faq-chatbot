# -*- coding: utf-8 -*-
"""학과 교무·생활 Q&A 챗봇 - Streamlit 화면.

실행:  streamlit run app.py
"""

import time
from pathlib import Path

import streamlit as st

from chat_logic import build_entry
from i18n import LANG_LABELS, LANGS, get_lang, t
from retriever import DEFAULT_FAQ_PATH, DEFAULT_THRESHOLD, Retriever, is_filled, load_faqs

st.set_page_config(
    page_title="학과 Q&A 챗봇 · 院系问答机器人",
    page_icon="💬",
    layout="centered",
)

STYLE_PATH = Path(__file__).with_name("styles.css")
st.html(f"<style>{STYLE_PATH.read_text(encoding='utf-8')}</style>")

# 화면에는 프로젝트 기준 상대 경로만 보여준다(전체 경로가 노출되지 않도록).
REL_FAQ_PATH = "data/faq.csv"
FAQ_DIR = DEFAULT_FAQ_PATH.parent.parent

# 처음 화면에 보여주는 예시 질문(눌러서 바로 질문). 시연 원문 그대로 사용한다.
EXAMPLE_QUESTIONS = ["휴학 신청은 언제 해요?", "什么时候选课？", "签证续签要多久"]


def resolve_faq_path(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else FAQ_DIR / p


@st.cache_resource(show_spinner=False)
def get_retriever(faq_path: str, method: str, threshold: float) -> Retriever:
    return Retriever(faqs=load_faqs(resolve_faq_path(faq_path)), threshold=threshold, method=method)


def render_source(faq, score: float, method: str) -> None:
    st.caption(
        t(
            "source",
            source=faq.source or t("source_unknown"),
            checked=faq.checked_at or t("checked_unknown"),
            id=faq.id,
            score=score,
            method=method,
        )
    )


def render_candidates(candidates) -> None:
    with st.expander(t("candidates")):
        for score, faq_id, question in candidates:
            st.write(f"{score:.3f} · {faq_id} · {question}")


def typewriter(text: str):
    """답변을 조금씩 보여주는 효과(전체 약 0.5초 안팎)."""
    delay = min(0.012, 1.0 / max(len(text), 1))
    for i in range(0, len(text), 2):
        yield text[i : i + 2]
        time.sleep(delay)


def say(text: str, stream: bool) -> None:
    if stream and text:
        st.write_stream(typewriter(text))
    else:
        st.markdown(text)


def question_button(idx: int, faq, prefix: str) -> None:
    text = (faq.variants(get_lang()) or faq.variants("ko"))[0] or faq.question_ko
    if st.button(text, key=f"{prefix}_{idx}_{faq.id}"):
        st.session_state.pending_prompt = text


def render_match(idx: int, entry: dict, stream: bool) -> None:
    faq = entry["faq"]
    reply, fell_back = faq.answer_for(entry.get("force_lang") or get_lang())
    if entry.get("lead"):
        st.markdown(t(entry["lead"]))
    if not is_filled(reply) or not faq.checked_at:
        st.markdown(f":orange-badge[{t('unverified')}]")
    say(reply, stream)
    if fell_back:
        st.caption(t("ko_original"))
    render_source(faq, entry["score"], entry["method"])
    if entry.get("related"):
        st.caption(t("related_label"))
        for rel in entry["related"]:
            question_button(idx, rel, "rel")


def render_none(idx: int, entry: dict, stream: bool) -> None:
    best = t("best_candidate", score=entry["best"]) if entry["best"] is not None else ""
    say(t("no_answer", best=best), stream)
    if entry["suggestions"]:
        st.caption(t("suggest_label"))
        for faq in entry["suggestions"]:
            question_button(idx, faq, "sug")


def render_entry(idx: int, entry: dict, show_debug: bool, stream: bool = False) -> None:
    """대화 기록 한 건을 현재 화면 언어로 다시 그린다(언어·검색방식을 바꿔도 출처 줄이 유지된다)."""
    with st.chat_message(entry["role"]):
        kind = entry.get("kind")
        if kind is None:  # 사용자 말풍선
            st.markdown(entry["text"])
        elif kind == "talk":
            say(t(entry["key"]), stream)
        else:
            (render_match if kind == "match" else render_none)(idx, entry, stream)
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
st.caption(t("disclaimer"))

typed = st.chat_input(t("chat_input"))

# 대화가 비어 있으면 예시 질문 버튼을 보여준다(질문이 들어오면 바로 숨긴다).
examples_box = st.empty()
if not st.session_state.history and "pending_prompt" not in st.session_state:
    with examples_box.container():
        with st.chat_message("assistant"):
            st.markdown(t("welcome"))
        st.caption(t("examples_label"))
        cols = st.columns(len(EXAMPLE_QUESTIONS))
        for col, question in zip(cols, EXAMPLE_QUESTIONS):
            if col.button(question, key=f"ex_{question}", use_container_width=True):
                st.session_state.pending_prompt = question

for i, entry in enumerate(st.session_state.history):
    render_entry(i, entry, show_debug)

prompt = st.session_state.pop("pending_prompt", None) or typed
if prompt:
    examples_box.empty()
    st.session_state.history.append({"role": "user", "text": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    entry = build_entry(prompt, st.session_state.history, index)
    st.session_state.history.append(entry)
    render_entry(len(st.session_state.history) - 1, entry, show_debug, stream=True)

st.divider()
st.caption(t("footer"))