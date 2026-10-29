# -*- coding: utf-8 -*-
"""실제 브라우저(Playwright)로 화면을 열어 AI 토글 문구를 검사하고 스크린샷을 남긴다. requirements.txt 에는 넣지 않는다.

AppTest(smoke_ui.py)는 서버 프로세스 하나를 새로 띄우는 것과 같아서, '서버를 켜 둔 채 i18n.py 가 바뀐' 상황이나
브라우저에 실제로 그려진 모습은 잡지 못한다. 이 스크립트는 진짜 서버를 띄우고 진짜 브라우저로 확인한다.

준비(한 번):  python -m venv <임시폴더>\\pwenv  →  <임시폴더>\\pwenv\\Scripts\\pip install playwright
              (Chromium 이 없으면 Windows 에 설치된 Edge/Chrome 을 자동으로 쓴다)
실행:         <pwenv>\\Scripts\\python screenshot_check.py [--out 폴더] [--prefix ai_fix] [--no-hotswap]

확인하는 것(한국어/中文 × 서버 미설정/설정됨(가짜 값, 실제 호출 없음)):
  - (추가) 가짜 응답으로 AI 답변을 그려 본다: URL 이 전각 부호·한자와 붙어 있어도 올바른 링크(href 가 ASCII 주소 그대로)로 나오고,
    中文 라벨이 "未经确认" 그대로이며, 날짜 답변이 끝까지 보이고, 학교와 무관한 질문이 FAQ 에 잘못 붙지 않는다
  - 하단 고정 영역(st.bottom)의 토글 라벨·도움말(?)·캡션이 i18n 문구와 같다
  - 화면 어디에도 i18n 키 이름(ai_toggle, ai_not_configured …)이 그대로 나오지 않는다
  - (기본) 서버를 켜 둔 채 i18n.py 를 바꿔도 새 문구가 나온다(임시 복사본에서 확인)
"""

import argparse
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from i18n import STRINGS  # noqa: E402  (streamlit 없이 import 가능)

ALL_KEYS = set(STRINGS["ko"]) | set(STRINGS["zh"])
FAKE_ENV = {"LLM_ENABLED": "on", "CLOUDFLARE_ACCOUNT_ID": "x", "CLOUDFLARE_API_TOKEN": "x"}  # 가짜 자리값
FAILS = []


def check(name, cond, detail=""):
    if cond:
        print(f"  OK   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        FAILS.append(name)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def project_python() -> str:
    cand = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return str(cand) if cand.exists() else sys.executable


class Server:
    """streamlit run app.py 를 임의의 빈 포트에 띄운다. 환경변수는 지정한 것만(기본: AI 관련 값 모두 제거)."""

    def __init__(self, cwd: Path, extra_env=None, script: str = "app.py"):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("LLM_", "CLOUDFLARE"))}
        env["PYTHONIOENCODING"] = "utf-8"
        env.update(extra_env or {})
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.proc = subprocess.Popen(
            [project_python(), "-m", "streamlit", "run", script, "--server.headless", "true",
             "--server.port", str(self.port), "--browser.gatherUsageStats", "false"],
            cwd=str(cwd), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(90):
            try:
                urllib.request.urlopen(self.url + "/_stcore/health", timeout=2)
                return
            except Exception:
                time.sleep(1)
        self.close()
        raise RuntimeError("streamlit 서버가 뜨지 않았습니다")

    def close(self):
        if os.name == "nt":  # 런처가 자식 프로세스를 만들기 때문에 트리째 끈다
            subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"], capture_output=True)
        else:
            self.proc.kill()


def launch(p):
    try:
        return p.chromium.launch()
    except Exception:
        for channel in ("msedge", "chrome"):
            try:
                return p.chromium.launch(channel=channel)
            except Exception:
                pass
        raise


JS_ALL_STRINGS = """() => {
  const out = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) { const v = w.currentNode.nodeValue.trim(); if (v) out.push(v); }
  for (const el of document.querySelectorAll('[aria-label],[title],[placeholder]')) {
    for (const a of ['aria-label', 'title', 'placeholder']) { const v = el.getAttribute(a); if (v) out.push(v.trim()); }
  }
  return out;
}"""


def open_page(browser, url, lang):
    page = browser.new_page(viewport={"width": 1000, "height": 900})
    page.goto(url)
    page.wait_for_selector("h1", timeout=60000)
    if lang == "zh":
        page.locator('[data-testid="stButtonGroup"] button', has_text="中文").first.click()
        page.wait_for_function("document.querySelector('h1').innerText.includes('院系')", timeout=30000)
    page.wait_for_timeout(1500)
    return page


def raw_key_hits(page):
    return sorted({s for s in page.evaluate(JS_ALL_STRINGS) if s in ALL_KEYS})


def help_text(page):
    icon = page.locator('[data-testid="stBottom"] [data-testid="stTooltipIcon"]').first
    icon.hover()
    box = page.locator('[data-testid="stTooltipContent"]').first
    box.wait_for(timeout=10000)
    return box.inner_text().strip()


def inspect(browser, url, lang, configured, out_dir, prefix, tag):
    S = STRINGS[lang]
    page = open_page(browser, url, lang)
    state = "configured" if configured else "notconfigured"
    name = f"{tag}/{lang}/{'서버 설정됨(가짜 값)' if configured else '서버 미설정'}"
    bottom = page.locator('[data-testid="stBottom"]')
    btext = bottom.inner_text()
    lines = [x.strip() for x in btext.splitlines() if x.strip()]
    toggle_input = bottom.locator('input[type="checkbox"]').first
    check(f"{name}: 하단 영역 토글 라벨 = i18n 문구", S["ai_toggle"] in lines, lines)
    check(f"{name}: 라벨이 키 이름(ai_toggle)이 아니다", "ai_toggle" not in lines, lines)
    if configured:
        check(f"{name}: 미설정 캡션 없음·토글 사용 가능", S["ai_not_configured"] not in lines and not toggle_input.is_disabled(), lines)
    else:
        check(f"{name}: 미설정 캡션 = i18n 문구", S["ai_not_configured"] in lines and "ai_not_configured" not in lines, lines)
        check(f"{name}: 토글 비활성", toggle_input.is_disabled())
    tip = help_text(page)
    check(f"{name}: 도움말(?) = i18n 문구(키 이름 아님)", tip == S["ai_toggle_help"] and tip != "ai_toggle_help", tip)
    page.mouse.move(0, 0)
    page.wait_for_timeout(300)
    check(f"{name}: 화면 어디에도 i18n 키 이름이 그대로 나오지 않는다", not raw_key_hits(page), raw_key_hits(page))
    if out_dir:
        path = Path(out_dir) / f"{prefix}_{lang}_{state}.png"
        page.screenshot(path=str(path))
        print(f"  saved {path}")
    if configured:  # 토글만 켠다(질문은 하지 않음 → 호출 없음). 켜면 안내 문구가 나온다.
        toggle_input.evaluate("el => el.click()")
        page.wait_for_function("(t) => document.querySelector('[data-testid=\"stBottom\"]').innerText.includes(t)",
                               arg=S["ai_on_notice"][:20], timeout=15000)
        lines = [x.strip() for x in bottom.inner_text().splitlines() if x.strip()]
        check(f"{name}: 토글을 켜면 안내 = i18n 문구", S["ai_on_notice"] in lines and "ai_on_notice" not in lines, lines)
        check(f"{name}: 켠 뒤에도 키 이름 없음", not raw_key_hits(page), raw_key_hits(page))
        if out_dir:
            path = Path(out_dir) / f"{prefix}_{lang}_{state}_on.png"
            page.screenshot(path=str(path))
            print(f"  saved {path}")
    page.close()


# --- 가짜 HTTP 로 AI 답변을 화면에 그려 보는 검사 -------------------------------------------------------------
# 서버 프로세스 안에서 llm_answer._http_post 만 가짜로 바꾸고 app.py 를 그대로 실행하는 러너. 실제 네트워크 호출은 없다.
RUNNER_SRC = r"""
import os, runpy, sys
ROOT = os.environ["FAQ_ROOT"]
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import llm_answer as la

REPLIES = [
    ("你是什么模型", "我是庆南大学留学生问答助手，背后用的是AI语言模型；具体模型名称为 @cf/google/gemma-4-26b-a4b-it。"),
    ("今天几号", "今天是 2026年10月29日，星期四。"),
    ("韩国手机卡怎么办", "可以去机场或运营商营业厅办理，详见学校官网（www.kyungnam.ac.kr）或 HiKorea（https://www.hikorea.go.kr），谢谢。"),
]


def fake_post(url, headers, payload, timeout):
    q = payload["messages"][-1]["content"]
    text = next((r for k, r in REPLIES if k in q), "这是一个测试回答。")
    return {"result": {"choices": [{"message": {"content": text}, "finish_reason": "stop"}], "usage": {"neurons": 1}}, "success": True}


la._http_post = fake_post
runpy.run_path(os.path.join(ROOT, "app.py"), run_name="__main__")
"""

JS_LINKS = """() => [...document.querySelectorAll('[data-testid="stChatMessage"] a')].map(a => [a.getAttribute('href'), a.innerText])"""


def ask(page, question, expect_text):
    box = page.locator('[data-testid="stChatInput"] textarea')
    box.fill(question)
    box.press("Enter")
    page.wait_for_function("(t) => document.body.innerText.includes(t)", arg=expect_text, timeout=30000)
    page.wait_for_timeout(1500)  # 글자가 조금씩 나타나는 효과(write_stream)가 끝날 때까지


def last_message(page):
    return page.locator('[data-testid="stChatMessage"]').last


def render_check(browser, out_dir, prefix):
    tmp = Path(tempfile.mkdtemp(prefix="faq_render_"))
    srv = None
    try:
        runner = tmp / "mock_runner.py"
        runner.write_text(RUNNER_SRC, encoding="utf-8")
        srv = Server(ROOT, {**FAKE_ENV, "LLM_RATE_PER_MIN": "30", "FAQ_ROOT": str(ROOT)}, script=str(runner))  # 가짜 응답이라 호출 제한을 풀어 둔다
        print(f"[가짜 AI 응답으로 화면 그리기] {srv.url}")
        page = open_page(browser, srv.url, "zh")
        S = STRINGS["zh"]
        html_translate = page.evaluate("document.documentElement.getAttribute('translate')")
        meta = page.evaluate("!!document.querySelector('meta[name=google][content=notranslate]')")
        check("자동 번역 방지 표시(translate=no, meta notranslate)", html_translate == "no" and meta, (html_translate, meta))
        page.locator('[data-testid="stBottom"] input[type="checkbox"]').first.evaluate("el => el.click()")
        page.wait_for_function("(t) => document.querySelector('[data-testid=\"stBottom\"]').innerText.includes(t)",
                               arg=S["ai_on_notice"][:12], timeout=15000)

        ask(page, "你是什么模型", "具体模型名称为")
        msg = last_message(page).inner_text()
        check("'你是什么模型': FAQ(F23)에 붙지 않고 AI 답변 라벨이 나온다", "F23" not in msg and "依据" not in msg and S["ai_label"] in msg, msg[:300])
        check("中文 라벨이 정확히 '未经确认' (默认确认 아님)", "AI自主回答，未经确认（FAQ中没有这个问题，由AI直接回答）" in msg and "默认确认" not in msg, msg[:300])
        check("'你是什么模型': 학교와 무관한 FAQ 제안이 붙지 않는다(你可能还想问 없음)", S["suggest_label"] not in msg, msg[-200:])

        ask(page, "今天几号", "星期四")
        msg = last_message(page).inner_text()
        check("'今天几号': 날짜 답변이 끝까지 보인다(2026年10月29日，星期四)", "今天是 2026年10月29日，星期四。" in msg, msg[:200])

        ask(page, "韩国手机卡怎么办", "谢谢")
        links = page.evaluate(JS_LINKS)[-3:]
        hrefs = [h for h, _ in links]
        check("AI 답변·안내 속 URL 링크 3개(官网 / HiKorea / 안내문구의 官网)", len(links) == 3, links)
        check("href 가 ASCII 주소 그대로(punycode·全角 글자 없음)",
              hrefs == ["https://www.kyungnam.ac.kr", "https://www.hikorea.go.kr", "https://www.kyungnam.ac.kr"], hrefs)
        msg = last_message(page).inner_text()
        check("URL 뒤의 全角 부호（）、，가 글자로 남는다", "（www.kyungnam.ac.kr）" in msg and "https://www.hikorea.go.kr），谢谢" in msg, msg[:300])
        if out_dir:
            path = Path(out_dir) / f"{prefix}_zh_render_ai.png"
            page.screenshot(path=str(path))
            print(f"  saved {path}")

        ask(page, "怎么登录学生信息系统", "确认日")
        links = page.evaluate(JS_LINKS)
        faq_links = links[-3:]
        bad = [h for h, _ in links if h and ("xn--" in h or re.search(r"[^\x00-\x7f]", h))]
        check("FAQ 답변·출처의 모든 링크에 punycode(xn--)·비ASCII 글자가 없다", not bad, bad)
        check("F23: 选课网址 링크가 https://sugang.kyungnam.ac.kr", any(h == "https://sugang.kyungnam.ac.kr" for h, _ in faq_links), faq_links)
        check("F23: 출처 URL 링크가 https://www.kyungnam.ac.kr/pdfView/... 그대로",
              any(h == "https://www.kyungnam.ac.kr/pdfView/international/49/fileDownload.do" for h, _ in faq_links), faq_links)
        page.close()
    finally:
        if srv:
            srv.close()
        shutil.rmtree(tmp, ignore_errors=True)


def sanitized_copy() -> Path:
    """프로젝트의 임시 복사본(.venv·.git·logs·reports 와 .streamlit/secrets.toml 은 제외). 'AI 서버 미설정' 상태를 이 PC 의 실제 설정과 무관하게 만든다."""
    tmp = Path(tempfile.mkdtemp(prefix="faq_clean_"))
    for item in ROOT.iterdir():
        if item.name in {".venv", "__pycache__", ".git", "reports", "logs"}:
            continue
        if item.is_dir():
            shutil.copytree(item, tmp / item.name, ignore=shutil.ignore_patterns("secrets.toml", "__pycache__"))
        else:
            shutil.copy2(item, tmp / item.name)
    return tmp


def hotswap(browser, out_dir, prefix):
    """실제 사고 재현: 서버가 옛 i18n.py 로 떠 있는 동안 파일을 새 것으로 바꾼다 → 새 세션에서 키 이름이 아닌 문구가 나와야 한다."""
    srv = None
    tmp = sanitized_copy()  # secrets.toml 은 복사하지 않는다
    try:
        full = (tmp / "i18n.py").read_text(encoding="utf-8")
        old = re.sub(r'^\s+"(ai_toggle|ai_toggle_help|ai_not_configured|ai_on_notice)":.*\n', "", full, flags=re.M)
        check("[준비] 옛 i18n(AI 키 없음)을 만들었다", old != full)
        (tmp / "i18n.py").write_text(old, encoding="utf-8")
        srv = Server(tmp)
        page = open_page(browser, srv.url, "ko")
        lines = [x.strip() for x in page.locator('[data-testid="stBottom"]').inner_text().splitlines() if x.strip()]
        check("[준비] 옛 i18n 로 뜬 서버: 키 이름이 보인다(사고 상태)", "ai_toggle" in lines, lines)
        page.close()
        time.sleep(1.5)
        (tmp / "i18n.py").write_text(full, encoding="utf-8")  # 서버는 그대로 두고 파일만 교체
        os.utime(tmp / "i18n.py", (time.time() + 5, time.time() + 5))
        time.sleep(1.5)
        S = STRINGS["ko"]
        page = open_page(browser, srv.url, "ko")
        lines = [x.strip() for x in page.locator('[data-testid="stBottom"]').inner_text().splitlines() if x.strip()]
        check("[수정] 서버를 다시 켜지 않아도 새 i18n 문구가 나온다(토글 라벨·캡션)",
              S["ai_toggle"] in lines and S["ai_not_configured"] in lines and not raw_key_hits(page), lines)
        if out_dir:
            path = Path(out_dir) / f"{prefix}_ko_hotswap_after.png"
            page.screenshot(path=str(path))
            print(f"  saved {path}")
        page.close()
    finally:
        if srv:
            srv.close()
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(Path.home() / "Downloads"), help="스크린샷 저장 폴더(기본: 다운로드)")
    ap.add_argument("--prefix", default="ai_fix", help="스크린샷 파일 이름 앞부분")
    ap.add_argument("--no-hotswap", action="store_true", help="i18n.py 교체 재현 검사를 건너뛴다")
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = launch(p)
        try:
            for configured in (False, True):
                clean = None if configured else sanitized_copy()  # 미설정 상태는 secrets.toml 없는 복사본에서 확인
                srv = Server(clean or ROOT, FAKE_ENV if configured else None)
                try:
                    print(f"[{'서버 설정됨(가짜 값)' if configured else '서버 미설정(기본)'}] {srv.url}")
                    for lang in ("ko", "zh"):
                        inspect(browser, srv.url, lang, configured, out_dir, args.prefix, "화면")
                finally:
                    srv.close()
                    if clean:
                        shutil.rmtree(clean, ignore_errors=True)
            render_check(browser, out_dir, args.prefix)
            if not args.no_hotswap:
                print("[서버를 켜 둔 채 i18n.py 교체]")
                hotswap(browser, out_dir, args.prefix)
        finally:
            browser.close()
    print()
    if FAILS:
        print(f"실패 {len(FAILS)}건: {FAILS}")
        sys.exit(1)
    print("모두 통과")


if __name__ == "__main__":
    main()
