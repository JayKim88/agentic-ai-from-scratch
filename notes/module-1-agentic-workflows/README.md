# Module 1 — 에이전틱 워크플로우 입문

DeepLearning.AI [Agentic AI](https://www.deeplearning.ai/courses/agentic-ai) 모듈 1 학습 정리.
원본 노트: [Notion — Agentic AI Note](https://app.notion.com/p/3b1e5ccd65b180109afdda0f9ea88052)

## 목차

| # | 레슨 | 핵심 내용 |
|---|---|---|
| 01 | [에이전틱 AI란 무엇인가](01-what-is-agentic-ai.md) | 선형 생성 vs 반복 워크플로우, 작업 분해가 핵심 스킬 |
| 02 | [자율성의 정도](02-degrees-of-autonomy.md) | "에이전트다/아니다"가 아닌 스펙트럼, 다이어그램 색상 규칙 |
| 03 | [에이전틱 AI의 이점](03-benefits.md) | HumanEval 데이터, 병렬성, 모듈성 |
| 04 | [활용 사례](04-applications.md) | 송장 처리 → 컴퓨터 사용까지 난이도 4단계 |
| 05 | [작업 분해](05-task-decomposition.md) | **이 모듈의 중심.** 분해 방법론과 빌딩 블록 |
| 06 | [평가 (evals)](06-evals.md) | 만든 뒤 발견하기, 객관적/주관적 eval, 오류 분석 |
| 07 | [에이전틱 디자인 패턴](07-design-patterns.md) | 리플렉션·도구 사용·계획·멀티 에이전트 |

## 모듈 1을 한 장으로

**1. 에이전틱 워크플로우란**
LLM 기반 앱이 하나의 작업을 완료하기 위해 **여러 단계를 실행하는 프로세스**.
한 번에 다 쓰는 대신, 초안 → 검토 → 수정을 반복한다.

**2. 왜 하는가**
GPT-3.5를 에이전틱 워크플로우로 감싸면 GPT-4의 비에이전틱 성능을 넘어선다.
**모델 세대 교체보다 워크플로우 설계의 효과가 더 크다.**

**3. 어떻게 만드는가**
"사람이라면 어떻게 할까?" → 단계로 나눈다 → 각 단계를 LLM/도구에 매핑한다
→ 안 되면 더 쪼갠다 → **반복한다.**

**4. 무엇이 어려운가**
절차가 미리 정해져 있지 않을 때, 그리고 입력이 텍스트가 아닐 때.

**5. 어떻게 개선하는가**
미리 예측하지 말고 **먼저 만들어 출력을 눈으로 본다.**
발견한 문제에 맞는 eval을 만들고, 트레이스로 오류 분석을 한다.

**6. 조합 도구 4가지**
리플렉션(Reflection) · 도구 사용(Tool Use) · 계획(Planning) · 멀티 에이전트(Multi-Agent)

## 강좌 전체에서 모듈 1의 위치

| 모듈 | 주제 | 모듈 1과의 연결 |
|---|---|---|
| **1** | **에이전틱 워크플로우 입문** | — |
| 2 | [Reflection](../module-2-reflection/README.md) | 07의 패턴 1, 05의 4~5단계를 심화 |
| 3 | Tool Use + MCP | 07의 패턴 2 |
| 4 | 평가·에러 분석·최적화 | **06을 본격적으로 확장** |
| 5 | Planning & Multi-Agent | 07의 패턴 3, 4 |

## 이미지

`images/` 안의 PNG 7장은 모두 **강의 슬라이드 캡처**다.
원본은 macOS 스크린샷(HEIC)이며, 마크다운에서 렌더링되지 않아 PNG로 변환해 저장했다.

| 파일 | 사용 위치 |
|---|---|
| `02-degrees-of-autonomy.png` | 02 — 낮은/높은 자율성 워크플로우 비교 |
| `04-invoice-workflow.png` | 04 — 송장 처리 |
| `04-customer-email-workflow.png` | 04 — 고객 이메일 응대 (사람 검토 포함) |
| `05-essay-decomposition-recap.png` | 05 — 직접 생성 → 3단계 → 5단계 |
| `05-customer-email-steps.png` | 05 — 3단계 분해와 단계별 LLM/도구 매핑 |
| `05-building-blocks.png` | 05 — 빌딩 블록 표 |
| `07-planning-hugginggpt.png` | 07 — HuggingGPT 계획 예시 |
