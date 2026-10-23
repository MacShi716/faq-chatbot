# -*- coding: utf-8 -*-
"""학과 교무·생활 Q&A 챗봇 - Streamlit 화면.

실행:  streamlit run app.py
"""

from pathlib import Path

import streamlit as st

from i18n import LANG_LABELS, LANGS, get_lang, t
from normalize import detect_lang
from retriever import DEFAULT_FAQ_PATH, DEFAULT_THRESHOLD, Retriever, load_faqs

st.set_page_config(
    page_title="학과 Q&A 챗봇 · 院系问答机器人",
    page_icon="💬",
    layout="centered",
)

# 화면에는 프로젝트 기준 상대 경로만 보여준다(전체 경로가 노출되지 않도록).
REL_FAQ_PATH = "data/faq.csv"
FAQ_DIR = DEFAULT_FAQ_PATH.parent.parent


def resolve_faq_path(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else FAQ_DIR / p


@st.cache_resource(show_spinner=False)
def get_retriever(faq_path: str, method: str, threshold: float) -> Retriever:
    return Retriever(faqs=load_faqs(resolve_faq_path(faq_path)), threshold=threshold, method=method)


def render_source(match) -> None:
    faq = match.faq
    st.caption(
        t(
            "source",
            source=faq.source or t("source_unknown"),
            checked=faq.checked_at or t("checked_unknown"),
            id=faq.id,
            score=match.score,
            method=match.method,
        )
    )


# --- 화면 언어 전환: 오른쪽 위, 작은 세그먼트 버튼 -------------------------------
_, lang_col = st.columns([1, 0.34])
with lang_col:
    picked = st.segmented_control(
        t("lang_label"),
        options=list(LANGS),
        format_func=lambda code: LANG_LABELS[code],
        default=get_lang(),
        label_visibility="collapsed",
        key="ui_lang_picker",
    )
if picked:
    st.session_state.ui_lang = picked
lang = get_lang()

with st.sidebar:
    st.header(t("settings"))
    faq_path = st.text_input(t("faq_file"), value=REL_FAQ_PATH)
    method = st.radio(
        t("search_method"),
        options=["difflib", "tfidf"],
        index=0,
        captions=[t("method_difflib"), t("method_tfidf")],
    )
    threshold = st.slider(t("threshold"), 0.1, 0.9, DEFAULT_THRESHOLD, 0.05)
    show_debug = st.checkbox(t("show_candidates"), value=False)

    try:
        index = get_retriever(faq_path, method, threshold)
        st.success(t("loaded", n=len(index.faqs)))
    except Exception as exc:  # 데이터 오류를 화면에서 바로 확인하기 위함
        st.error(t("load_error", err=exc))
        st.stop()

st.title(t("title"))
st.caption(t("disclaimer"))

if "history" not in st.session_state:
    st.session_state.history = []

for role, text in st.session_state.history:
    with st.chat_message(role):
        st.markdown(text)

if prompt := st.chat_input(t("chat_input")):
    st.session_state.history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)

    q_lang = detect_lang(prompt)
    match = index.answer(prompt, lang=q_lang)

    with st.chat_message("assistant"):
        if match is None:
            candidates = index.search(prompt, lang=q_lang, top_k=1)
            best = t("best_candidate", score=candidates[0].score) if candidates else ""
            reply = t("no_answer", best=best)
            st.markdown(reply)
        else:
            reply, fell_back = match.faq.answer_for(lang)
            st.markdown(reply)
            if fell_back:
                st.caption(t("ko_original"))
            render_source(match)
            if show_debug:
                with st.expander(t("candidates")):
                    for cand in index.search(prompt, lang=q_lang, top_k=3):
                        st.write(f"{cand.score:.3f} · {cand.faq.id} · {cand.faq.question_ko}")

    st.session_state.history.append(("assistant", reply))

st.divider()
st.caption(t("footer"))
