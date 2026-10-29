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
_MD_ESCAPE = re.compile(r"([\\`*_{}\[\]<>~$])")
# safe_links 가 만든 [표시](<주소>) 링크 (표시 글자 안의 \[ \] 같은 이스케이프 포함).
# 앞에 \ 가 붙은 '\[' 는 글자 그대로의 [ 라 링크의 시작이 아니다(쪼개면 타이핑 도중 \ 가 보인다).
_MD_LINK = re.compile(r"(?<!\\)\[(?:\\.|[^\[\]\\])*\]\(<[^>]*>\)")

# --- 마크다운 특수 문자 이스케이프 (QA AC-1 3차, 2026-10-29) ---------------------------------------------------
# Streamlit 의 st.markdown·st.write_stream·st.caption·st.write·버튼 라벨은 마크다운(GFM)으로 그린다.
# 그래서 FAQ 답변의 '9/1~9/28' 처럼 물결표(~)가 두 번 나오면 그 사이가 취소선이 되고 ~ 는 사라지며('9/19/28'),
# '$' 두 개 사이는 수식(LaTeX)으로 그려진다. 데이터(faq.csv)는 그대로 두고 화면에 그릴 때만 이스케이프한다.
# - "data"(FAQ 답변·출처·질문·사용자 말풍선): 마크다운으로 쓴 글이 아니므로 특수 문자를 모두 글자 그대로 보이게 한다.
# - "ai"(AI 답변): 굵게·목록 같은 마크다운을 일부러 쓰므로 잘못 그려지는 ~(취소선)·$(수식)만 이스케이프한다.
# URL 은 safe_links 와 똑같이 [표시](<주소>) 링크로 바꾸고(표시 글자도 이스케이프), <주소> 안은 건드리지 않는다.
_MD_DATA = re.compile(r"([\\`*_{}\[\]<>~$#|])")
_MD_AI = re.compile(r"([~$])")
# 줄 맨 앞의 목록·제목 표시('- ', '+ ', '1. ', '1) ', '===', '---'): "data" 글에서는 글자 그대로 보이게 한다.
# (숫자 목록은 숫자 뒤 '.' ')' 를 이스케이프한다: '\1' 처럼 숫자 앞 \ 는 이스케이프가 아니라 글자로 보인다.)
_LINE_START = re.compile(r"(^|\n)([ \t]*)(?:([-+=])|(\d+)([.)]))")


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


def _to_md_link(m: re.Match) -> str:
    """URL 매치를 [표시](<주소>) 로 바꾸거나, 건너뛰면 원래 글자를 돌려준다."""
    url, tail = _split_trailing(m.group(0))
    if not url or url.lower() in ("http://", "https://", "www."):
        return m.group(0)
    href = url if url.lower().startswith("http") else "https://" + url
    return f"[{_MD_ESCAPE.sub(r'\\\1', url)}](<{href}>){tail}"


def safe_links(text: str) -> str:
    """맨 URL 을 [표시](<주소>) 로 바꾼다. 이미 마크다운 링크이거나 <주소> 안에 있는 것은 그대로 둔다."""
    if not text or ("http" not in text.lower() and "www." not in text.lower()):
        return text
    return _URL.sub(_to_md_link, text)


def _escape_line_start(m: re.Match) -> str:
    lead = m.group(1) + m.group(2)
    return lead + ("\\" + m.group(3) if m.group(3) else m.group(4) + "\\" + m.group(5))


def escape_markdown(text: str, mode: str = "data", line_start: bool = True) -> str:
    r"""URL 이 없는 글의 마크다운 특수 문자 앞에 \ 를 붙인다. mode: "data"(전부) / "ai"(~ 와 $ 만).

    line_start=False 면 글의 맨 앞은 줄의 시작이 아니다(URL 바로 뒤 조각): 줄바꿈 뒤만 목록·제목 표시를 본다.
    """
    if not text:
        return text
    if mode == "ai":
        return _MD_AI.sub(r"\\\1", text)
    text = _MD_DATA.sub(r"\\\1", text)
    if not line_start:
        head, nl, rest = text.partition("\n")
        return head + nl + _LINE_START.sub(_escape_line_start, rest) if nl else text
    return _LINE_START.sub(_escape_line_start, text)


def safe_markdown(text: str, mode: str = "data") -> str:
    """화면에 그릴 글: URL 은 [표시](<주소>) 링크로, 나머지 글은 escape_markdown(mode).

    mode "ui" 는 화면 문구(i18n, 일부러 쓴 마크다운 포함)라 링크만 바꾼다(= safe_links).
    """
    if mode == "ui" or not text:
        return safe_links(text)
    out, pos = [], 0
    for m in _URL.finditer(text):
        linked = _to_md_link(m)
        if linked == m.group(0):
            continue
        tail = _split_trailing(m.group(0))[1]
        out += [escape_markdown(text[pos : m.start()], mode, line_start=pos == 0), linked[: len(linked) - len(tail)]]
        pos = m.end() - len(tail)  # 뗀 문장부호는 다음 글과 함께 이스케이프한다
    out.append(escape_markdown(text[pos:], mode, line_start=pos == 0))
    return "".join(out)


def typing_chunks(text: str, size: int = 2) -> list[str]:
    r"""타자 효과용 조각(size 글자씩). [표시](<주소>) 링크와 '\~' 같은 이스케이프는 쪼개지 않고 한 조각으로 둔다.

    두 글자씩 자르면 타이핑 도중 '[www.kyungnam.ac.kr](<https' 같은 마크다운 원문이 잠깐 보인다.
    """
    text = text or ""

    def pieces(plain: str) -> list[str]:
        # '\~' 같은 이스케이프(\ + 다음 글자)는 한 글자처럼 센다: 쪼개면 타이핑 도중 \ 가 보이거나 ~ 가 취소선이 된다.
        units = re.findall(r"\\.|.", plain, re.DOTALL)
        return ["".join(units[i : i + size]) for i in range(0, len(units), size)]

    out, pos = [], 0
    for m in _MD_LINK.finditer(text):
        out += pieces(text[pos : m.start()]) + [m.group(0)]
        pos = m.end()
    return out + pieces(text[pos:])
