# -*- coding: utf-8 -*-
"""언어 감지와 문자열 정규화.

FAQ 검색의 품질은 대부분 "비교 전에 문장을 얼마나 잘 정리하는가"에서 갈린다.
똑같은 질문도 띄어쓰기·문장부호·조사가 다르면 difflib 유사도가 크게 떨어진다.
"""

import re
import unicodedata

# 중국어 판별: 한자만 있으면 중국어로 본다.
_HANZI = re.compile(r"[\u4e00-\u9fff]")
_HANGUL = re.compile(r"[\uac00-\ud7a3]")

# 비교 전에 제거할 문장부호 (한국어/중국어/영문 공통)
_PUNCT = re.compile(r"[\s\.\,\?\!~。、，？！；;:：'\"“”‘’\(\)\[\]\{\}<>《》·…\-_/\\|]+")


def detect_lang(text: str) -> str:
    """질문 언어를 반환한다: 'ko' 또는 'zh'.

    한글이 하나라도 있으면 한국어로 본다(한국어 문장에 한자가 섞이는 경우가 있다).
    """
    if _HANGUL.search(text):
        return "ko"
    if _HANZI.search(text):
        return "zh"
    return "ko"  # 숫자·영문만 있는 경우는 한국어 기본값


def normalize(text: str) -> str:
    """유사도 비교용 정규화 문자열을 만든다.

    - 유니코드 정규화(NFKC): 전각 문자/호환 문자를 반각으로
    - 소문자화
    - 공백과 문장부호 제거
    """
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    text = _PUNCT.sub("", text)
    return text


def split_variants(value: str) -> list[str]:
    """CSV 한 칸에 '|' 로 구분해 넣은 동의어 표현을 나눈다."""
    if not value:
        return []
    return [v.strip() for v in str(value).split("|") if v.strip()]
