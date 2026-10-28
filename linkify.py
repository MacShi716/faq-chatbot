# -*- coding: utf-8 -*-
"""화면에 보여 줄 글 안의 URL 을 안전하게 만든다.

Streamlit(마크다운)은 "www.kyungnam.ac.kr）확인" 처럼 URL 바로 뒤에 전각 문장부호·한자·한글이 붙으면
그 글자까지 주소로 보고 링크를 만든다. 그러면 링크가 `xn--...` 같은 깨진 주소(punycode)가 된다.
여기서는 글 속의 맨 URL 을 ASCII 문자만으로 된 명시적 마크다운 링크 [주소](<주소>) 로 바꿔서
뒤에 어떤 글자가 붙어도 링크 범위가 URL 자체로 끝나게 한다. 데이터(faq.csv)는 건드리지 않고 화면에 그릴 때만 쓴다.
"""

from __future__ import annotations

import re

# ASCII 주소 문자만(한글·한자·전각 부호는 주소에 포함하지 않는다).
_URL = re.compile(
    r"(?<![A-Za-z0-9_@/<\[\]])(?<!\]\()(?:https?://|www\.)[A-Za-z0-9\-._~:/?#@!$&*+,;=%\[\]()']+(?!\]\()",
    re.IGNORECASE,
)
_TRAIL = ".,;:!?'"
_MD_ESCAPE = re.compile(r"([\\`*_{}\[\]<>])")


def _split_trailing(url: str) -> tuple[str, str]:
    """URL 끝에 붙은 문장부호(. , ; : ! ? ' 와 짝이 없는 ) ])는 URL 에서 뗀다."""
    tail = ""
    while url:
        ch = url[-1]
        if ch in _TRAIL or (ch == ")" and url.count(")") > url.count("(")) or (ch == "]" and url.count("]") > url.count("[")):
            tail, url = ch + tail, url[:-1]
        else:
            break
    return url, tail


def safe_links(text: str) -> str:
    """맨 URL 을 [표시](<주소>) 로 바꾼다. 이미 마크다운 링크이거나 <주소> 안에 있는 것은 그대로 둔다."""
    if not text or ("http" not in text.lower() and "www." not in text.lower()):
        return text

    def repl(m: re.Match) -> str:
        url, tail = _split_trailing(m.group(0))
        if not url or url.lower() in ("http://", "https://", "www."):
            return m.group(0)
        href = url if url.lower().startswith("http") else "https://" + url
        label = _MD_ESCAPE.sub(r"\\\1", url)
        return f"[{label}](<{href}>){tail}"

    return _URL.sub(repl, text)
