# -*- coding: utf-8 -*-
"""화면 문구 다국어 사전 (한국어 / 中文).

새 문구를 추가할 때는 두 언어를 반드시 같이 넣는다.
데이터(FAQ 답변)는 번역하지 않는다. 화면 UI 만 바뀐다.
"""

STRINGS = {
    "ko": {
        "page_title": "학과 교무·생활 Q&A 챗봇",
        "lang_label": "언어",
        "title": "학과 교무·생활 Q&A 챗봇",
        "disclaimer": "※ 답변이 정확하지 않을 수 있습니다. 중요한 내용은 학과 사무실에 확인하세요.",
        "settings": "설정",
        "faq_file": "FAQ 파일",
        "search_method": "검색 방식",
        "method_difflib": "1단계 · 문자열 유사도",
        "method_tfidf": "2단계 · TF-IDF",
        "threshold": "임계값 (이 값 미만이면 답변하지 않음)",
        "show_candidates": "상위 후보 보기",
        "loaded": "FAQ {n}건 로드됨",
        "load_error": "FAQ 파일을 읽지 못했습니다: {err}",
        "chat_input": "궁금한 내용을 입력하세요 (한국어 / 中文)",
        "no_answer": "죄송합니다. 질문에 맞는 답변을 찾지 못했습니다.{best}\n\n학과 사무실에 문의해 주세요.",
        "best_candidate": " (가장 유사한 후보 유사도 {score:.2f})",
        "source": "근거: {source} · 확인일 {checked} · FAQ {id} · 유사도 {score:.2f} ({method})",
        "source_unknown": "출처 미등록",
        "checked_unknown": "미확인",
        "candidates": "상위 후보",
        "footer": "데이터 담당: FAQ 의 answer/source/checked_at 를 실제 확인 내용으로 채운 뒤 사용하세요.",
    },
    "zh": {
        "page_title": "院系教务与生活问答机器人",
        "lang_label": "语言",
        "title": "院系教务与生活问答机器人",
        "disclaimer": "※ 回答可能不准确。重要事项请务必向系办公室确认。",
        "settings": "设置",
        "faq_file": "FAQ 文件",
        "search_method": "检索方式",
        "method_difflib": "第 1 阶段 · 字符串相似度",
        "method_tfidf": "第 2 阶段 · TF-IDF",
        "threshold": "阈值（低于该值不作答）",
        "show_candidates": "查看候选",
        "loaded": "已加载 FAQ {n} 条",
        "load_error": "无法读取 FAQ 文件：{err}",
        "chat_input": "请输入你想了解的内容（中文 / 한국어）",
        "no_answer": "抱歉，没有找到匹配的回答。{best}\n\n请咨询系办公室。",
        "best_candidate": "（最接近的候选相似度 {score:.2f}）",
        "source": "依据：{source} · 确认日 {checked} · FAQ {id} · 相似度 {score:.2f}（{method}）",
        "source_unknown": "未登记出处",
        "checked_unknown": "未确认",
        "candidates": "候选结果",
        "footer": "数据负责人：请把 FAQ 的 answer/source/checked_at 换成实际核实的内容后再使用。",
    },
}

LANGS = ("ko", "zh")
# 전환 버튼은 두 언어를 같이 보여준다. 한쪽만 알아도 자기 언어를 찾을 수 있게.
LANG_LABELS = {"ko": "한국어", "zh": "中文"}


def get_lang() -> str:
    """세션에 저장된 화면 언어. 없으면 한국어."""
    import streamlit as st

    lang = st.session_state.get("ui_lang")
    return lang if lang in LANGS else "ko"


def t(key: str, **kwargs) -> str:
    """현재 화면 언어의 문구를 돌려준다. 없는 키는 키 이름을 그대로 보여준다(디버깅용)."""
    template = STRINGS[get_lang()].get(key) or STRINGS["ko"].get(key) or key
    return template.format(**kwargs) if kwargs else template
