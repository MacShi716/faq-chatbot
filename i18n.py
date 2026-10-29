# -*- coding: utf-8 -*-
"""화면 문구 다국어 사전 (한국어 / 中文).

새 문구를 추가할 때는 두 언어를 반드시 같이 넣는다.
데이터(FAQ 답변)는 번역하지 않는다. 화면 UI 만 바뀐다.
"""

STRINGS = {
    "ko": {
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
        "ko_original": "(한국어 원문)",
        "examples_label": "예시 질문 (눌러서 바로 질문)",
        "clear": "대화 지우기",
        "advanced": "고급 설정",
        "unverified": "⚠️ 미확인 답변 · 학과 사무실에서 확인하세요",
        "suggest_label": "혹시 이런 질문인가요?",
        "chips": "한국어 · 中文 질문 가능|FAQ 답변엔 출처·확인일, AI 답변엔 별도 라벨 표시|유학생 학사·생활 Q&A",
        "welcome": "안녕하세요! 무엇이 궁금하세요? 아래 질문을 눌러 보거나 직접 입력해 보세요.",
        "talk_greet": "안녕하세요! 학과 교무·생활 안내 챗봇이에요. 휴학, 수강신청, 기숙사, 비자 연장처럼 궁금한 걸 편하게 물어보세요. 한국어와 中文 모두 괜찮아요.",
        "talk_thanks": "도움이 되었다면 다행이에요. 다른 궁금한 점이 있으면 편하게 물어보세요.",
        "talk_bye": "네, 안녕히 가세요! 중요한 내용은 학과 사무실에서 꼭 한 번 더 확인해 주세요.",
        "talk_help": "저는 학과 FAQ에서 비슷한 질문을 찾아, 근거(출처·확인일)와 함께 알려드려요. FAQ 답변은 지어내지 않고, 확인되지 않은 내용은 '미확인'이라고 표시해요. FAQ에 없는 질문은 찾지 못했다고 안내하거나, 입력창 바로 위의 'AI 대화 켜기'를 켜면(서버에 AI 기능이 설정된 경우) 'AI 자율 답변'으로 따로 표시해 드려요(확인되지 않은 내용이니 꼭 학과 사무실에서 다시 확인하세요). '더 알려줘', '중국어로' 같은 이어지는 요청은 FAQ 답변에만 쓸 수 있어요.",
        "talk_ai_followup": "AI 자율 답변은 다시 보여주거나 번역하는 기능이 없어요. 궁금한 내용을 다시 입력해 주세요.",
        "ai_label": "🤖 AI 자율 답변 · 확인되지 않음 (FAQ에 없는 질문이라 AI가 직접 답했어요)",
        "ai_nudge": "정확하지 않을 수 있어요. 중요한 내용은 학과 사무실 또는 학교 공식 페이지 www.kyungnam.ac.kr 에서 꼭 확인하세요.",
        "ai_model": "모델: {model}",
        "ai_unavailable": "지금은 AI 답변을 가져오지 못했어요. 잠시 뒤 다시 시도하거나 학과 사무실에 문의해 주세요.",
        "ai_toggle": "🤖 AI 대화 켜기 (FAQ에 없는 질문에 AI가 답해요)",
        "ai_toggle_help": "AI 답변은 확인되지 않은 내용이라 틀릴 수 있어요. 중요한 내용은 학과 사무실이나 학교 공식 페이지에서 꼭 확인하세요.",
        "ai_not_configured": "AI 기능이 서버에 설정되지 않았습니다",
        "ai_on_notice": "AI 답변은 확인되지 않은 내용입니다. 개인정보(전화번호·학번·이메일 등)는 입력하지 마세요. 질문이 외부 AI 서비스(Cloudflare Workers AI 등)로 전송될 수 있어요.",
        "school_fact_template": "이 정보는 FAQ에 아직 없어요. 학교 공식 페이지나 해당 사무실에 직접 확인해 주세요.",
        "talk_no_context": "아직 앞선 질문이 없어서 이어서 답하기 어려워요. 궁금한 내용을 먼저 입력해 주세요.",
        "lead_found": "관련 안내를 찾았어요.",
        "followup_note": "방금 안내한 내용을 다시 보여드려요. 세부 내용은 학과 사무실에서 한 번 더 확인해 주세요.",
        "related_label": "이런 질문도 많이 해요",
        "footer": "데이터 담당: FAQ 의 answer/source/checked_at 를 실제 확인 내용으로 채운 뒤 사용하세요.",
    },
    "zh": {
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
        "ko_original": "（韩语原文）",
        "examples_label": "示例问题（点击即可提问）",
        "clear": "清空对话",
        "advanced": "高级设置",
        "unverified": "⚠️ 未核实的回答 · 请向系办公室确认",
        "suggest_label": "你是不是想问：",
        "chips": "支持韩语 · 中文提问|FAQ回答附出处与确认日，AI回答另有标注|留学生教务·生活问答",
        "welcome": "你好！想了解什么？可以点下面的问题，也可以直接输入。",
        "talk_greet": "你好！我是院系教务与生活问答机器人。休学、选课、宿舍、签证续签等问题都可以直接问我，韩语和中文都行。",
        "talk_thanks": "能帮到你就好。还有别的问题随时问我。",
        "talk_bye": "好的，再见！重要事项记得再向系办公室确认一下。",
        "talk_help": "我会在院系 FAQ 里找相近的问题，并附上出处和确认日期。FAQ 回答不会乱编，没核实过的内容会标成“未核实”。FAQ 里没有的问题，我会告诉你没找到；如果在输入框上方开启了AI对话（需服务器已配置AI功能），则会单独标注为“AI自主回答”（内容未经确认，请务必再向系办公室确认）。“再详细点”“用韩语”这类追问只适用于 FAQ 回答。",
        "talk_ai_followup": "AI自主回答不支持再次展示或翻译，请重新输入你想问的内容。",
        "ai_label": "🤖 AI自主回答，未经确认（FAQ中没有这个问题，由AI直接回答）",
        "ai_nudge": "可能不准确。重要事项请务必向系办公室或学校官网 www.kyungnam.ac.kr 确认。",
        "ai_model": "模型：{model}",
        "ai_unavailable": "暂时无法获取AI回答，请稍后再试或咨询系办公室。",
        "ai_toggle": "🤖 开启AI对话（FAQ里没有的问题由AI回答）",
        "ai_toggle_help": "AI回答未经核实，可能有误。重要事项请务必向系办公室或学校官网确认。",
        "ai_not_configured": "服务器未配置AI功能",
        "ai_on_notice": "AI回答未经确认。请不要输入个人信息（电话、学号、邮箱等）。你的提问可能会被发送到外部AI服务（Cloudflare Workers AI 等）。",
        "school_fact_template": "FAQ里还没有这条信息，请向学校官网或相关办公室确认。",
        "talk_no_context": "目前还没有上一个问题，没法接着回答。请先输入你想问的内容。",
        "lead_found": "找到了相关的回答。",
        "followup_note": "这是刚才那条回答的再次展示，细节请再向系办公室确认。",
        "related_label": "你可能还想问：",
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
