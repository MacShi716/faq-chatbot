# -*- coding: utf-8 -*-
"""화면이 실제로 동작하는지 확인하는 UI 스모크 테스트.

Streamlit 공식 테스트 하네스(AppTest)로 app.py 를 그대로 실행한다.
    python smoke_ui.py
"""

import sys

from streamlit.testing.v1 import AppTest

FAILS = []


def check(name, cond, detail=""):
    if cond:
        print(f"  OK   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        FAILS.append(name)


def all_text(at) -> str:
    parts = [m.value for m in at.markdown]
    parts += [c.value for c in at.caption]
    return "\n".join(parts)


print("[1] 앱 기동 (기본 한국어)")
at = AppTest.from_file("app.py", default_timeout=60)
at.run()
check("예외 없음", not at.exception, at.exception)
check("한국어 제목", "학과 교무·생활" in "\n".join(x.value for x in at.title), [x.value for x in at.title])
check("사이드바 라디오 존재", len(at.radio) >= 1)
check("언어 전환 위젯 존재", len(at.get("segmented_control")) >= 1)

print("[2] 한국어 질문")
at.chat_input[0].set_value("휴학 신청은 언제 해요?").run()
check("예외 없음", not at.exception, at.exception)
text = all_text(at)
check("답변 표시", "F01" in text, text[:200])

print("[3] 중국어 질문")
at.chat_input[0].set_value("什么时候选课？").run()
check("예외 없음", not at.exception, at.exception)
text = all_text(at)
check("중국어 처리", "F04" in text, text[-200:])

print("[4] 화면 언어를 中文 으로 전환")
at.get("segmented_control")[0].set_value("zh")
at.run()
check("예외 없음", not at.exception, at.exception)
check("중국어 제목", "院系教务" in "\n".join(x.value for x in at.title), [x.value for x in at.title])
check("중국어 사이드바", "设置" in "\n".join(x.value for x in at.header), [x.value for x in at.header])

print("[5] 전환 후에도 질문 동작")
at.chat_input[0].set_value("宿舍费用多少").run()
check("예외 없음", not at.exception, at.exception)
check("중국어 안내 문구", "没有找到" in all_text(at) or "통과" in "", all_text(at)[-200:])

print()
if FAILS:
    print(f"실패 {len(FAILS)}건: {FAILS}")
    sys.exit(1)
print("모두 통과")
