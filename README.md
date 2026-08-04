# Agentic AI — 로컬 실습 환경

DeepLearning.AI [**Agentic AI**](https://www.deeplearning.ai/courses/agentic-ai) (Andrew Ng) 강의의
ungraded 코드 예제를 로컬에서 실행하기 위한 작업 공간.

> 채점 과제(graded assignment) 8개는 DLAI 플랫폼에서만 제출 가능하다.
> 이 레포는 **ungraded 코드 예제 7개**를 로컬에서 돌려보는 용도.

## 강의 개요

| 항목 | 내용 |
|---|---|
| 강사 | Andrew Ng |
| 난이도 | Intermediate |
| 분량 | 약 9시간 55분 / 영상 31개 |
| 실습 | 코드 예제 7개(ungraded), 채점 과제 8개(Pro) |
| 선수지식 | 중급 Python, LLM/API 기본 이해 |

### 커리큘럼

| 모듈 | 주제 | 핵심 개념 |
|---|---|---|
| 1 | Introduction to Agentic Workflows | task decomposition, 자율성 수준 |
| 2 | Reflection | 자기 비평으로 출력 개선 |
| 3 | Tool Use | 툴 제작, 코드 실행, MCP 프로토콜 |
| 4 | Practical Tips | 평가(evals), 에러 분석, 최적화 |
| 5 | Highly Autonomous Agents | Planning, Multi-Agent |
| 최종 | Research Agent | 정보 수집 → 분석 → 리포트 생성 |

**핵심 철학:** 프레임워크(LangChain / CrewAI / AutoGen) 없이 **밑바닥부터 직접 구현**.
`requirements.txt`에 해당 프레임워크가 하나도 없는 것이 그 증거다.

## 학습 정리

| 모듈 | 정리 | 상태 |
|---|---|---|
| 1 | [에이전틱 워크플로우 입문](notes/module-1-agentic-workflows/README.md) | ✅ 레슨 7개 완료 |
| 2 | [리플렉션 디자인 패턴](notes/module-2-reflection/README.md) | ✅ 레슨 7개 완료 (랩 2개는 🔒 Pro 전용) |
| 3 | Tool Use | 예정 |
| 4 | Practical Tips (evals) | 예정 |
| 5 | Planning & Multi-Agent | 예정 |

출처는 Notion 원본 노트([Agentic AI - Note](https://app.notion.com/p/3b1e5ccd65b180109afdda0f9ea88052))이며,
한국어 본문 + 강의 슬라이드 캡처로 재구성했다.

## 직접 구현한 프로젝트

무료 티어에서는 **랩 실행 환경(Pro 전용)에 접근할 수 없다.**
따라서 직접 구현하고, 채점은 자체 eval로 대체한다.

| 프로젝트 | 대응 | 출발점 | 상태 |
|---|---|---|---|
| [research-agent](projects/research-agent/README.md) | 모듈 1 "Try the research agent" | **강의 영상만** | ✅ 완료 — 자체 평가 8/8 |
| [chart-agent](projects/chart-agent/README.md) | 모듈 2 "Chart Generation" | **랩 자료 확보** | 🔨 3/7단계 |

두 프로젝트의 성격이 다르다. 모듈 1은 랩을 못 봐서 **백지에서 설계**했고,
모듈 2는 랩 자료(`labs/module-2/`)를 얻어 **명세가 있는 재현**이다.

| 회고 | 내용 |
|---|---|
| [자체 구현 vs 공식 저장소](notes/retrospectives/research-agent-vs-official.md) | 모듈 1 — 완성 후 공식 저장소와 대조 |
| [차트 에이전트 랩 대조](notes/retrospectives/chart-agent-lab-findings.md) | 모듈 2 — 진행 중. 반성이 차트를 퇴행시킨 실물 사례 |

프레임워크(LangChain / CrewAI) 없이 도구 호출 루프까지 직접 구현했다.

---

## 환경 세팅

이미 세팅 완료. 아래는 재현 절차.

```bash
# 1. venv 생성 — Python 3.12 사용 (3.13 아님, 아래 "버전 선택" 참고)
/opt/homebrew/bin/python3.12 -m venv venv

# 2. 활성화
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. 설치
pip install --upgrade pip
pip install -r requirements.txt

# 4. Jupyter 커널 등록
python -m ipykernel install --user --name=venv --display-name="Python (agentic-ai)"
```

### 현재 상태

| 항목 | 값 |
|---|---|
| Python | 3.12.11 (Homebrew) |
| venv 경로 | `./venv` |
| Jupyter 커널 | `venv` / 표시 이름 `Python (agentic-ai)` |
| 검증 | 전체 top-level import 통과, `pip check` 무결 |

### 버전 선택 이유

시스템 기본은 Python 3.13.1이지만 **3.12.11을 사용**한다.
강의 요구사항은 3.10+ 이고, 3.13은 일부 패키지가 wheel 대신 소스 빌드로 떨어질 위험이 있다.

---

## 실행 방법

### VSCode (권장)

`.ipynb` 파일을 열고 우측 상단 커널 선택 → **`Python (agentic-ai)`**

### 브라우저

```bash
source venv/bin/activate
jupyter notebook
```

두 방식 모두 동일한 venv 커널을 사용한다.
VSCode 사용 시 `notebook` / `jupyter_server` / `nbclassic`은 실제로 로드되지 않고,
`ipykernel`과 `ipywidgets`만 동작한다.

---

## 환경 변수

프로젝트 루트에 `.env` 생성. `python-dotenv`가 노트북에서 로드한다.

```dotenv
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
MISTRAL_API_KEY=...
```

- 전부 필요한 것은 아니다. 랩이 `aisuite`로 어떤 모델을 지정하느냐에 따라 다르다.
- `vertexai`를 쓰는 랩이 있다면 `GOOGLE_APPLICATION_CREDENTIALS`로 서비스 계정 JSON 경로 지정 필요.
- **`.env`와 노트북 출력에 키가 남지 않도록 주의.** 커밋 전 출력 셀 확인.

---

## 알려진 이슈

### nltk 3.10+ 임포트 차단 → `nltk<3.10` 고정

`import textstat`이 `ImportError: Blocked import of regex from current working directory`로 실패한다.

**원인:** nltk 3.10에 추가된 임포트 가드(`nltk/inisec.py`)가
"nltk가 유발한 import 중 모듈 경로가 **cwd 또는 그 하위**에 있으면 차단"하는데,
판정이 단순 경로 접두사 비교라서 `./venv/lib/.../site-packages/`도 걸린다.
venv를 프로젝트 안에 두는 표준 관행이 그대로 오탐 대상이 된다.

**시도했으나 무효:** `PYTHONSAFEPATH=1`.
그 옵션은 `sys.path[0]`에서 cwd를 제거할 뿐, 이 가드는 `sys.path`와 무관하게 경로를 직접 비교한다.

**채택한 해법:** `requirements.txt`에 `nltk<3.10` 고정 (설치된 버전 3.9.4).
→ **이 핀을 풀지 말 것.** 풀면 textstat이 다시 깨진다.

**대안:** venv를 프로젝트 밖(`~/.venvs/agentic-ai`)에 두면 최신 nltk로도 동작한다.
프로젝트 내 venv 관행을 유지하기 위해 채택하지 않았다.

### 버전 주의: pandas 3.x

pip가 pandas 3.0.5 / numpy 2.5.1을 설치했다.
강의 노트북이 pandas 2.x 기준으로 작성됐다면 chained assignment, `inplace=`,
dtype 자동 승격 관련 동작 변경으로 깨질 수 있다.
문제 발생 시 첫 조치: `pip install "pandas<3"`

---

## 디렉터리 구조 (제안)

노트북을 내려받으면 모듈별로 분리한다.

```
agentic-ai/
├── README.md
├── CLAUDE.md
├── requirements.txt
├── .env                    # git 제외
├── venv/                   # git 제외
├── notes/                  # 강의 학습 정리 (한국어)
│   ├── module-1-agentic-workflows/
│   │   ├── README.md       # 모듈 인덱스 + 한 장 요약
│   │   ├── 01~07-*.md      # 레슨별 정리
│   │   └── images/         # 강의 슬라이드 캡처 (PNG)
│   ├── module-2-reflection/
│   │   └── (동일 구조)
│   └── retrospectives/     # 자체 구현 vs 공식 구현 비교
├── projects/               # 직접 구현한 프로젝트
│   ├── research-agent/     # 모듈 1 리서치 에이전트
│   └── chart-agent/        # 모듈 2 차트 에이전트
└── labs/                   # 강의 자료 원본 (수정 금지)
    └── module-2/           # 노트북 HTML · coffee_sales.csv · 차트 2장
```

| 디렉터리 | 역할 |
|---|---|
| `notes/` | 읽고 이해한 내용 |
| `projects/` | 직접 만든 코드 |
| `labs/` | 강의가 제공하는 자료 원본 — **무료 티어에서는 실행 환경에 접근 불가** |

> **노트북 다운로드 시 주의:** 강의 플랫폼에서 `File > Open`으로 들어가
> 노트북뿐 아니라 **헬퍼 스크립트·설정 파일·데이터 파일까지 함께** 받아야 한다.
> 같은 랩의 부속 파일은 같은 디렉터리에 둔다.

---

## 패키지 맵

강의 모듈과 `requirements.txt`의 대응 관계.

**확정** 표시는 공식 리서치 에이전트 저장소
([https-deeplearning-ai/agentic-ai-public](https://github.com/https-deeplearning-ai/agentic-ai-public))의
`requirements.txt`와 대조해 확인한 항목이다. 나머지는 패키지 성격에서 추론한 것.

| 모듈 | 패키지 | 역할 | 근거 |
|---|---|---|---|
| 전 구간 | `aisuite` + `anthropic` `openai` `mistralai` `vertexai` | 모델 교체만 추상화. 에이전트 로직은 직접 구현 | 확정 (`aisuite`, `openai`) |
| 2. Reflection | `textstat` | 가독성 점수 — 자기 비평의 객관적 판정 기준 | 추정 |
| 3. Tool Use | `docstring-parser` | **핵심.** docstring → JSON Schema 자동 변환 (함수를 툴로 등록) | 확정 |
| 3. Tool Use | `tavily-python` `Wikipedia` `requests` | 웹 검색·정보 수집 툴 | 확정 |
| 3. Tool Use | `qrcode` | 부수효과(side-effecting) 툴 예제 | 추정 |
| 4. 평가 | `pandas` `matplotlib` `seaborn` `tabulate` | 실행 로그 분석·시각화. 이 모듈의 본체 | 추정 |
| 5. Planning | `pydantic` | 계획·에이전트 간 메시지를 구조화 스키마로 강제 | 추정 |
| **최종 프로젝트** | `fastapi` `uvicorn` `jinja2` | **리서치 에이전트는 웹 서비스다.** `/generate_report`로 워크플로우 실행, `/task_progress/{id}`로 진행 상황 조회, Jinja2 템플릿으로 UI 렌더링 | 확정 |
| **최종 프로젝트** | `sqlalchemy` `psycopg2-binary` | 작업 상태·결과를 Postgres에 저장 | 확정 |
| 최종 프로젝트 | `markdown` | 리포트 렌더링 | 추정 |
| 실습 UI | `ipywidgets` | 노트북 내 에이전트 대화 인터페이스 | 추정 |
| 미확정 | `duckdb` `python-multipart` | DB 조회 툴 예제 / 파일 업로드로 추정 | 추정 |
| 의존성 | `nltk` | textstat이 요구. 직접 사용 안 함 | — |

### 눈에 띄는 공백

1. **`mcp` 패키지 없음** — 모듈 3에 MCP 프로토콜이 명시돼 있으나 SDK가 requirements에 없다.
   해당 레슨이 개념 위주이거나 노트북 내에서 별도 설치할 가능성.
2. **벡터 DB·임베딩 라이브러리 전무** — chromadb, faiss 등이 없다.
   이 강의는 RAG 강의가 아니며, `scikit-learn`은 유사도 계산 보조 역할로 보인다.
3. **공식 저장소에는 있으나 코스 requirements에 없는 것** — `pdfminer.six`, `pymupdf`.
   리서치 에이전트가 PDF에서 텍스트를 추출한다는 뜻이다. 최종 프로젝트를 로컬에서
   재현하려면 별도 설치가 필요할 수 있다.

---

## 참고 저장소

### [https-deeplearning-ai/agentic-ai-public](https://github.com/https-deeplearning-ai/agentic-ai-public)

DeepLearning.AI **공식 계정**이 공개한 리서치 에이전트 서비스.
"Try the research agent" 레슨에서 시연되는 바로 그 앱이다.

```
main.py, Dockerfile
src/  ├── agents.py           실행 에이전트 (research / writing / editing)
      ├── planning_agent.py   플래너
      └── research_tools.py   Tavily · arXiv · Wikipedia 도구
templates/, static/, docker/
```

FastAPI + Postgres 단일 컨테이너. 실행에 Docker와 `OPENAI_API_KEY`, `TAVILY_API_KEY`가 필요하다.

> ⚠ **라이선스가 명시돼 있지 않다.** 공개 저장소이므로 읽고 학습하는 것은 문제없으나,
> 명시적 라이선스 부재는 기본적으로 "모든 권리 유보"를 뜻한다. 코드를 자기 프로젝트로
> 가져가 재배포하는 것은 별개 문제다.

### 랩 노트북은 GitHub에 없다

랩 노트북 자체의 공식 GitHub 배포는 **존재하지 않는다.**
([커뮤니티 스레드](https://community.deeplearning.ai/t/is-the-code-for-the-agentic-ai-labs-available-on-github-or-elsewhere/881171) — 학생 질문에 스태프 답변 없음)
노트북은 플랫폼에서 `File > Open`으로 직접 받아야 한다.

수강생이 올린 비공식 미러(`totola/agentic-ai-course`, `nhatnam2609/agentic_ai_andrew`)가
존재하지만 출처·라이선스가 불명확하므로 위 공식 저장소를 우선한다.
