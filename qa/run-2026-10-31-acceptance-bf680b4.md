# 인수 검증 리포트 — 2026-10-31 (로컬 Streamlit)

- 검증 시각(KST): 2026-10-31 01:06
- 대상 커밋: `bf680b4` (main)
- 대상 URL: `http://127.0.0.1:8501` (로컬 Streamlit, `_gh_rewrite` 기준으로 재기동)
- 실행 도구: `dsh-qa-acceptance` / `qa_run.py`
- 체크리스트: `qa/faq.yaml` (이 파일과 같은 폴더)
- 판정: **PASS (5/5)**

## 1. 결과

| ID | 유형 | 결과 | 소요 | 내용 |
| --- | --- | --- | ---: | --- |
| http-health | http | PASS | 55 ms | `/_stcore/health` → 200 `ok` |
| http-home | http | PASS | 28 ms | `/` → 200, `Streamlit` 포함 |
| console-home | console | PASS | 779 ms | 데스크톱·모바일 2 뷰포트, 콘솔 오류 0 |
| flow-suggestion-question | flow | PASS | 2417 ms | 제안 질문 클릭 → 제안 목록이 사라짐 |
| flow-chat-input-visible | flow | PASS | 2755 ms | 모바일에서 입력창 표시, `h1` 에 `Q&A` 포함 |

브라우저 뷰포트: 데스크톱 1280×800, 모바일 390×844.

## 2. 추가 확인(수동, 같은 빌드)

QA 러너의 흐름 검사는 "제안 버튼이 사라졌는지"까지만 본다. 답변 내용은 별도로 확인했다.

- 제안 질문 `휴학 신청은 언제 해요?` 클릭 후 6초 뒤 본문 전체 렌더링 확인
  - `관련 안내를 찾았어요.` + `⚠️ 미확인 답변 · 학과 사무실에서 확인하세요`
  - 답변 본문(일반휴학 절차·기간·한도) 정상 표시
  - 출처 줄: `근거: 휴학 안내(경남대학교 학적) https://... ; ... · 확인일 미확인 · FAQ F01 · 유사도 1.00 (difflib)`
- 사이드바: `FAQ 85건 로드됨`
- AI 토글: 기본 꺼짐 + 안내 `AI 기능이 서버에 설정되지 않았습니다` (자격 없을 때 비활성 요구사항 충족)
- 안내 칩: `한국어 · 中文 질문 가능` / `FAQ 답변엔 출처·확인일, AI 답변엔 별도 라벨 표시` / `유학생 학사·생활 Q&A`

## 3. 이 리포트가 대체하는 것

같은 체크리스트로 2026-10-31 00:52(KST)에 만든 PASS 리포트가 있었으나,
그 대상 Streamlit 프로세스는 **2026-10-29 01:25 기동**으로 `bf680b4`(10-29 23:40)보다 먼저 떠 있었다.
`@st.cache_resource` 때문에 모듈 변경이 반영되지 않는 상태였으므로 **증거로 쓰지 않는다.**
이 리포트는 `_gh_rewrite`(bf680b4)를 기준으로 프로세스를 재기동한 뒤 측정한 값이다.

## 4. 한계

- **AI 답변 경로는 미검증**: 서버 자격(`secrets.toml`)이 없어 토글을 켤 수 없다. AI 답변 라벨·미확인 표시는 별도 검증 필요.
- 이 리포트는 **화면·HTTP 인수 검증**일 뿐, 검색 정확도나 데이터 정확성을 보증하지 않는다.
- 내부 평가(`evaluate.py`, 47/50)와는 다른 축이다. 평가셋 편향 경고는 그대로 유효하다.
- 체크리스트는 `ACCEPTANCE.md` 가 없어 `README.md` 기준으로 추론한 5개 항목이다. AC-1~AC-5 요구사항과 1:1 대응하지 않는다.
- 스크린샷은 공개 저장소 정책상 커밋하지 않는다(로컬 보관).

## 5. 재현

```powershell
cd D:\cxdownload\创意综合设计\_gh_rewrite
$env:PYTHONIOENCODING='utf-8'
D:\cxdownload\创意综合设计\faq-chatbot\.venv\Scripts\python.exe -m streamlit run app.py --server.headless true --server.port 8501

# 다른 창에서
cd C:\Users\31508\.dsh\skills\dsh-qa-acceptance
D:\Python\python.exe qa_run.py D:\cxdownload\创意综合设计\_gh_rewrite\qa\faq.yaml --out D:\cxdownload\创意综合设计\_tmp\qa-faq
```

- 러너는 `D:\Python\python.exe`(playwright 1.64.1)에서 실행한다. 브라우저는 `%LOCALAPPDATA%\ms-playwright` 에 이미 있음.
- 앱은 `streamlit 1.66.1` 이 설치된 프로젝트 venv로 띄운다.
