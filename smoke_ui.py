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


print("[1] 앱 기동")
at = AppTest.from_file("app.py", default_timeout=60)
at.run()
check("예외 없음", not at.exception, at.exception)
check("사이드바 라디오 존재", len(at.radio) >= 1)

print("[2] 한국어 질문")
at.chat_input[0].set_value("휴학 신청은 언제 해요?").run()
check("예외 없음", not at.exception, at.exception)
text = "\n".join(m.value for m in at.markdown)
check("답변 표시", "F01" in text or "휴학" in text, text[:200])

print("[3] 중국어 질문")
at.chat_input[0].set_value("什么时候选课？").run()
check("예외 없음", not at.exception, at.exception)
text = "\n".join(m.value for m in at.markdown)
check("중국어 처리", "F04" in text or "选课" in text or "학과" in text, text[-200:])

print()
if FAILS:
    print(f"실패 {len(FAILS)}건: {FAILS}")
    sys.exit(1)
print("모두 통과")
