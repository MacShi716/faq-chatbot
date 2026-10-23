# -*- coding: utf-8 -*-
"""학과 교무·생활 Q&A 챗봇 - Streamlit 화면.

실행:  streamlit run app.py
"""

import streamlit as st

from normalize import detect_lang
from retriever import DEFAULT_FAQ_PATH, DEFAULT_THRESHOLD, Retriever, load_faqs

st.set_page_config(page_title="학과 교무·생활 Q&A 챗봇", page_icon="💬", layout="centered")

DISCLAIMER = "※ 답변이 정확하지 않을 수 있습니다. 중요한 내용은 학과 사무실에 확인하세요."


@st.cache_resource(show_spinner=False)
def get_retriever(faq_path: str, method: str, threshold: float) -> Retriever:
    return Retriever(faqs=load_faqs(faq_path), threshold=threshold, method=method)


def render_source(match) -> None:
    faq = match.faq
    st.caption(
        f"근거: {faq.source or '출처 미등록'} · 확인일 {faq.checked_at or '미확인'} "
        f"· FAQ {faq.id} · 유사도 {match.score:.2f} ({match.method})"
    )


with st.sidebar:
    st.header("설정")
    faq_path = st.text_input("FAQ 파일", value=str(DEFAULT_FAQ_PATH))
    method = st.radio("검색 방식", options=["difflib", "tfidf"], index=0,
                      captions=["1단계 · 문자열 유사도", "2단계 · TF-IDF"])
    threshold = st.slider("임계값 (이 값 미만이면 답변하지 않음)", 0.1, 0.9, DEFAULT_THRESHOLD, 0.05)
    show_debug = st.checkbox("상위 후보 보기", value=False)

    try:
        index = get_retriever(faq_path, method, threshold)
        st.success(f"FAQ {len(index.faqs)}건 로드됨")
    except Exception as exc:  # 데이터 오류를 화면에서 바로 확인하기 위함
        st.error(f"FAQ 파일을 읽지 못했습니다: {exc}")
        st.stop()

st.title("학과 교무·생활 Q&A 챗봇")
st.caption(DISCLAIMER)

if "history" not in st.session_state:
    st.session_state.history = []

for role, text in st.session_state.history:
    with st.chat_message(role):
        st.markdown(text)

if prompt := st.chat_input("궁금한 내용을 입력하세요 (한국어 / 中文)"):
    st.session_state.history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)

    lang = detect_lang(prompt)
    match = index.answer(prompt, lang=lang)

    with st.chat_message("assistant"):
        if match is None:
            candidates = index.search(prompt, lang=lang, top_k=1)
            best = f" (가장 유사한 후보 유사도 {candidates[0].score:.2f})" if candidates else ""
            reply = f"죄송합니다. 질문에 맞는 답변을 찾지 못했습니다.{best}\n\n학과 사무실에 문의해 주세요."
            st.markdown(reply)
        else:
            reply = match.faq.answer
            st.markdown(reply)
            render_source(match)
            if show_debug:
                with st.expander("상위 후보"):
                    for cand in index.search(prompt, lang=lang, top_k=3):
                        st.write(f"{cand.score:.3f} · {cand.faq.id} · {cand.faq.question_ko}")

    st.session_state.history.append(("assistant", reply))

st.divider()
st.caption("데이터 담당: FAQ 의 answer/source/checked_at 를 실제 확인 내용으로 채운 뒤 사용하세요.")
