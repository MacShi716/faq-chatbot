# 학과 교무·생활 Q&A 챗봇

> ※ FAQ 편집 중

> **AI 자율 답변(Tier B, 선택 기능 · 기본은 꺼짐)** — 서버에 설정해 두고 사용자가 앱 채팅 입력창 바로 위(화면 맨 아래에 입력창과 함께 고정)의 **"🤖 AI 대화 켜기"** 토글을 직접 켜면(세션마다 기본 꺼짐) FAQ에 매칭되지 않는 질문에 한해 무료 LLM(Cloudflare Workers AI, 429/5xx/시간 초과 때 Groq 폴백)이 직접 답한다. 이 답변에는 항상 "🤖 AI 자율 답변 · 확인되지 않음" 라벨이 붙고 출처·확인일은 없으며, FAQ 답변(Tier A)과 달리 정확도로 세지 않는다. 학교 고유 정보(전화·비용·일정·장소·운영시간)를 묻는 질문은 LLM을 부르지 않고 "FAQ에 아직 없어요, 공식 페이지나 해당 사무실에 확인해 주세요"만 안내한다. 질문 속 전화번호·이메일·긴 숫자(학번)는 가려서 보내고, 호출 기록은 `logs/tier_b.jsonl`(Git 제외)에 남는다. **키는 코드·`.env.example`·README 에 절대 쓰지 않고** 환경변수 또는 `.streamlit/secrets.toml`(Git 제외)에만 둔다. 켜는 방법은 아래 "AI 자율 답변 켜기" 참고.

경남대학교 소프트웨어융합학부 캡스톤디자인(종합설계) · 산학협력프로젝트
**2026.10.10 ~ 2026.12.15**

유학생이 학과 공지·교무 규정·졸업 요건·생활 정보를 **한국어 또는 중국어**로 물으면,
미리 구축한 FAQ 에서 가장 유사한 질문을 찾아 **답변 + 출처 + 확인일** 을 함께 보여주는 웹 챗봇.

- 1단계: `difflib` 문자열 유사도 (규칙 기반, 외부 API 없이 동작)
- 2단계: `scikit-learn` TF-IDF 코사인 유사도 + (선택) LLM/RAG

---

## 1. 빠른 시작 (5분)

```bash
# 1) 저장소 클론 후 폴더로 이동
cd faq-chatbot

# 2) 가상환경 생성 및 활성화 (Windows)
python -m venv .venv
.venv\Scripts\activate

# 3) 라이브러리 설치
pip install -r requirements.txt

# 4) 자체 점검 — 여기서 모두 통과해야 다음 단계로 간다
python selftest.py

# 5) 실행
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 이 열린다.

화면 오른쪽 위의 `한국어 | 中文` 버튼으로 UI 언어를 바꾼다. 질문 언어는 버튼과 무관하게
자동으로 판별된다(한국어로 물으면 한국어 FAQ, 中文으로 물으면 中文 FAQ 와 매칭).

> 답변 본문은 아직 한국어 데이터만 있다. 화면 문구만 번역되고 답변은 한국어로 나온다.
> 대응하려면 `faq.csv` 에 `answer_zh` 컬럼을 추가해야 한다(2주차 논의 안건).

### AI 자율 답변 켜기 (선택, PowerShell)

기본값은 꺼짐이라 아무것도 설정하지 않으면 지금까지와 똑같이(FAQ 답변 또는 "찾지 못했습니다") 동작한다.
이 앱은 `.env` 파일을 자동으로 읽지 않으므로, 아래 둘 중 하나로 설정한다. 값은 **절대 커밋하지 않는다**.

```powershell
# 방법 1) 현재 PowerShell 창에서만 유효한 환경변수
$env:LLM_ENABLED = "on"
$env:CLOUDFLARE_ACCOUNT_ID = "<Cloudflare 계정 ID>"
$env:CLOUDFLARE_API_TOKEN = "<Workers AI 토큰>"
# (선택) 폴백: $env:GROQ_API_KEY = "<Groq 키>"
streamlit run app.py
```

```toml
# 방법 2) .streamlit/secrets.toml  (.gitignore 로 제외됨)
LLM_ENABLED = "on"
CLOUDFLARE_ACCOUNT_ID = "<Cloudflare 계정 ID>"
CLOUDFLARE_API_TOKEN = "<Workers AI 토큰>"
```

#### 앱에서 AI 대화 켜고 끄기 (사용자 토글)

AI 기능은 **서버 설정**과 **사용자 선택** 두 단계로 켜진다.

1. **서버(운영자)**: 위 환경변수 또는 `.streamlit/secrets.toml` 에 `LLM_ENABLED = "on"` 과 제공자 키(Cloudflare 또는 Groq)를 설정한다. 키는 절대 코드·README·`.env.example` 에 쓰지 않는다.
2. **사용자**: 앱 채팅 입력창 바로 위(화면 맨 아래에 입력창과 함께 고정)의 **"🤖 AI 대화 켜기 (FAQ에 없는 질문에 AI가 답해요)"** 토글을 켠다. 토글은 브라우저 세션마다 **기본 꺼짐**이다(새로고침하면 다시 꺼짐).

- 토글을 켜는 순간 "AI 답변은 확인되지 않은 내용이며, 개인정보는 입력하지 말고, 질문이 외부 AI 서비스(Cloudflare Workers AI 등)로 전송될 수 있다"는 안내가 한 번 뜨고, 켜 둔 동안 토글 아래에 같은 안내가 작게 남는다.
- 서버에 AI 설정이 없으면(`LLM_ENABLED` 가 꺼짐이거나 키가 하나도 없음) 토글은 비활성으로 보이고 "AI 기능이 서버에 설정되지 않았습니다"가 표시된다. 키 값은 화면에 나오지 않는다.
- 토글이 꺼져 있으면 FAQ 에 없는 질문은 예전과 똑같이 "찾지 못했습니다"로 안내되고 LLM 은 호출되지 않는다(평가 점수에도 영향 없음).
- 이미 나온 AI 답변은 토글을 껐다 켜거나 화면 언어를 바꿔도 기록 그대로 다시 그려지며 LLM 을 다시 부르지 않는다. 세션당 분당 호출 제한과 캐시는 그대로다.

모델은 `LLM_MODEL`(기본 `@cf/google/gemma-4-26b-a4b-it`), Groq 는 `GROQ_MODEL`(기본 `openai/gpt-oss-120b`),
세션당 분당 호출 수는 `LLM_RATE_PER_MIN`(기본 2)으로 바꾼다. 전체 목록은 `.env.example` 참고.

AI 답변 동작(2026-10-29 개선):
- 시스템 프롬프트에 **오늘 날짜(Asia/Seoul)** 와 설정된 **모델 ID** 가 들어간다. 날씨·뉴스 같은 실시간 정보는 모른다고 답하고, 학교 정보는 지어내지 않으며, 질문한 언어로 완결된 문장으로 답한다. `max_tokens` 는 1000 이다.
- 날짜가 답에 들어갈 수 있어 캐시는 날짜별로 나뉜다.
- AI 대화가 켜져 있으면, FAQ 와 "무엇인가요/어떻게 해요" 같은 흔한 의문 표현만 겹치는 우연한 일치(예: "你是什么模型" → F23)는 매칭으로 보지 않고 AI 로 보낸다. 토글이 꺼져 있으면 이 판단은 쓰지 않아 예전 동작과 평가 점수(`evaluate.py`)가 그대로다.
- 화면에 그릴 때 글 속 URL 을 `[주소](<주소>)` 형태의 명시적 링크로 바꾼다(`linkify.py`). 전각 쉼표·괄호·한자가 URL 바로 뒤에 붙어도 링크가 깨지지 않는다. `faq.csv` 는 고치지 않아도 된다.

무료(Workers Free)로 쓸 수 있는 모델 비교(2026-10-29, 질문 6~12개 실측, 호출당 뉴런은 평균):
| `LLM_MODEL` | 호출당 뉴런 | 평균 응답 | 비고 |
|---|---|---|---|
| `@cf/google/gemma-4-26b-a4b-it` (기본, 생각 끔) | 약 5 | 약 3초 | 가장 싸고 빠름. 모르면 모른다고 답하는 편(짧고 보수적) |
| `@cf/openai/gpt-oss-120b` (추론 low) | 약 28 | 약 4초 | 가장 정보가 풍부하고 정확. 하루 무료 한도(10,000 뉴런)로 약 350회 |
| `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | 약 28 | 약 2초 | 무난하나 URL 을 지어낼 수 있음 |
| `@cf/qwen/qwen3.8-27b` (생각 끔) | 약 30 | 약 3초 | 비싼 편이고 D-2 근로시간을 틀리게 답함 |
| `@cf/zai-org/glm-4.7-flash` | 약 33 | 약 24초 | 너무 느리고 한국어에 한자가 섞임 |
Kimi·GLM-5.x·DeepSeek-V4 계열은 Workers Free 에서 "not available on the Workers Free plan"(403)이라 쓸 수 없다.
더 풍부한 답이 필요하면 `LLM_MODEL=@cf/openai/gpt-oss-120b` 로 바꾸면 된다(코드가 모델에 맞는 추론 옵션을 자동으로 붙인다).
자동 테스트(`selftest.py`, `smoke_ui.py`)는 HTTP 를 가짜로 바꿔 실행하므로 키 없이도 통과하고 실제 호출은 하지 않는다.

## 2. 폴더 구조

```
faq-chatbot/
├─ app.py            # Streamlit 채팅 화면
├─ i18n.py           # 화면 문구 사전 (한국어 / 中文) + 우측 상단 언어 전환
├─ retriever.py      # 검색 엔진 (difflib / TF-IDF)
├─ llm_answer.py     # Tier B: FAQ 에 없는 질문에 AI 자율 답변 (기본 꺼짐, 표준 라이브러리만 사용)
├─ normalize.py      # 언어 감지 + 문자열 정규화
├─ linkify.py        # 화면에 그릴 때 글 속 URL 을 안전한 링크로 바꿈(전각 부호·한자와 붙어도 안 깨짐)
├─ evaluate.py       # 50문항 정확도 측정 + 결과 보고서 생성
├─ tune.py           # 임계값 민감도 실험 (0.3 ~ 0.6)
├─ validate_data.py  # faq.csv 품질 점검 (ERROR / WARN)
├─ selftest.py       # 의존성 없는 자체 점검
├─ smoke_ui.py       # 화면 동작 스모크 테스트 (Streamlit AppTest)
├─ data/
│  ├─ faq.csv        # question_ko, question_zh, answer, source, checked_at
│  └─ eval.csv       # 평가 문항 50개 (한국어 25 / 중국어 25)
├─ docs/
│  ├─ 실행계획.md      # 주차별 일정
│  ├─ 데이터수집_가이드.md
│  └─ 회의록.md
└─ requirements.txt
```

## 3. 데이터 규칙 (가장 중요)

`data/faq.csv` 한 행이 FAQ 1건이다.

| 컬럼 | 의미 | 규칙 |
|---|---|---|
| `id` | FAQ 번호 | `F01`, `F02` … 중복 금지 |
| `question_ko` | 한국어 질문 | **동의어·다른 표현을 `|` 로 구분해 3~5개** |
| `question_zh` | 중국어 질문 | `|` 로 구분해 1~2개 |
| `answer` | 답변(한국어) | 실제 확인한 내용. 모르면 `[작성 필요]` 로 남긴다 |
| `answer_zh` | 답변(중국어) | 中文 화면에서 우선 표시. 비어 있으면 한국어로 폴백, `[작성 필요]` 면 중국어 초안으로 표시(미확인 배지) |
| `source` | 출처 | 문서명/공지 번호 (예: `학과 공지 2026-○○호`) |
| `checked_at` | 확인일 | `2026-10-25` 형식 |
| `category` | 분류 | 학사/장학/생활 |
| `tags` | 키워드 | **한국어·중국어를 섞어 `|` 로 5~10개**. 중국어 질문이 한국어 FAQ 에 붙는 다리 |

예시:

```csv
F01,휴학 신청은 언제 해요?|휴학하려면 어떻게 해야 돼?,什么时候可以申请休学？,휴학 신청 기간은 …(실제 확인 내용),休学申请期间为 …（实际核实内容）,학과 공지 2026-12호,2026-10-25,학사
```

> ⚠️ `answer` 가 `[작성 필요]` 인 상태로 발표하지 않는다. 출처가 없는 답변은 만들지 않는다.
> `answer_zh` 가 `[작성 필요]` 초안이면 中文 화면에 그대로(미확인 배지와 함께) 나오고, 완전히 비어 있을 때만 한국어 원문이 `（韩语原文）` 표시와 함께 나온다.

## 4. 정확도 측정

```bash
python evaluate.py --method difflib
python evaluate.py --method tfidf
```

결과는 `reports/eval-<방식>-<시각>.md` 에 저장되고, 언어별 정확도와 오답 목록이 함께 나온다.
계획서 기준: **50문항(한국어 25 / 중국어 25), 1단계 정확도 70% 이상**.
정확도는 FAQ 검색(Tier A)만 잰다. AI 자율 답변(Tier B)은 확인되지 않은 답변이라 집계에 넣지 않는다.

## 5. 팀 규칙

- 하루 작업이 끝나면 `commit` + `push`. 커밋 메시지는 한 줄로 "무엇을 했는지".
- 같은 파일을 두 사람이 동시에 고치지 않는다 (파일 단위로 작업을 나눈다).
- 회의 내용은 `docs/회의록.md` 에 남긴다 → 결과보고서 "수행과정"에 그대로 쓴다.
- API 키는 환경변수 또는 `.streamlit/secrets.toml` 에만(`.env` 를 써도 되지만 앱이 자동으로 읽지는 않는다). 모두 `.gitignore` 에 등록되어 있다.
- 최종 제출물(보고서·발표자료·화면 문구)은 **한국어**로 정리한다. 내부 문서는 중국어 허용.

## 6. 中文快速说明

项目：为留学生提供**韩语/中文**的院系教务与生活问答机器人（Streamlit）。
流程：`python -m venv .venv` → 激活 → `pip install -r requirements.txt` → `python selftest.py` → `streamlit run app.py`。

数据格式见第 3 节：`question_ko` 用 `|` 分隔 3~5 种韩语说法，`question_zh` 用 `|` 分隔 1~2 种中文说法，
`answer` 必须写**实际核实过的内容**，并留下 `source`（出处）和 `checked_at`（确认日期）。
未核实的答案保持 `[작성 필요]`，不要凭印象填写。

AI对话（可选）：服务器配置 `LLM_ENABLED=on` 和密钥后，用户需在聊天输入框正上方（与输入框一起固定在页面底部）手动打开“🤖 开启AI对话”开关（每个会话默认关闭），FAQ里没有的问题才会由AI回答，并带“未经确认”标签；未配置时开关为灰色。
