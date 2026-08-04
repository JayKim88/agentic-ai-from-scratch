# Module 2 — 리플렉션 디자인 패턴 (Reflection Design Pattern)

DeepLearning.AI [Agentic AI](https://www.deeplearning.ai/courses/agentic-ai) 모듈 2 학습 정리.
원본 노트: [Notion — Module 2: Reflection Design Pattern](https://app.notion.com/p/3b1e5ccd65b18022bdb7c777ff8b9fef)

## 목차

| # | 레슨 | 핵심 내용 |
|---|---|---|
| 01 | [리플렉션으로 결과물 개선하기](01-reflection-basics.md) | 기본 워크플로우, 단계별로 다른 모델, **외부 피드백이 판을 바꾼다** |
| 02 | [왜 직접 생성으로는 부족한가](02-why-not-direct-generation.md) | 제로/원/퓨샷 용어, Madaan et al. 근거, 좋은 검토 프롬프트 쓰는 법 |
| 03 | [차트 생성 워크플로우](03-chart-generation-workflow.md) | 멀티모달 LLM이 **그림을 보고** 비평, 누적 막대 → 분리 막대 |
| 04 | [Ungraded Lab: Chart Generation](04-lab-chart-generation.md) | 🔒 Pro 전용 — 슬라이드에서 유추한 내용 |
| 05 | [리플렉션의 효과 평가하기](05-evaluating-reflection.md) | **이 모듈에서 가장 실용적.** 객관/주관 평가, 위치 편향, 루브릭 채점 |
| 06 | [외부 피드백 활용하기](06-using-external-feedback.md) | 정체기 돌파, 피드백 소스 3종, 다음 모듈(도구 사용)로 연결 |
| 07 | [Ungraded Lab: SQL + Reflection](07-lab-sql-reflection.md) | 🔒 Pro 전용 — 슬라이드에서 유추한 내용 |

## 모듈 2를 한 장으로

**1. 리플렉션이란**
LLM에게 자기 출력을 검토·수정하게 하는 것. 사람이 이메일 초안을 고쳐 쓰는 것과 같다.

**2. 왜 하는가**
제로샷 프롬프팅보다 **일관되게 더 높은 성능**이 나온다 (Madaan et al.).
다만 **마법은 아니다** — "적당한 수준의 향상"이 정직한 표현이다.

**3. 어떻게 잘 하는가**
`"검토해줘"` ❌ → **구체적 평가 기준을 명시하라** ✅
검토 단계에는 **추론(reasoning) 모델**을 쓰면 더 낫다.

**4. 텍스트만이 아니다**
멀티모달 LLM에 **생성된 이미지를 직접 보여주면** 코드만 읽어서는 못 잡는 결함을 잡는다.

**5. 유지할지는 재보고 결정하라**
리플렉션은 단계를 늘리고 느리게 만든다.
객관적 평가 → 정답 데이터셋 + 정확도 (87% → 95%)
주관적 평가 → **쌍대비교 말고 루브릭.** 이진 기준을 합산하라.

**6. 진짜 도약은 외부 피드백에서 온다**
```
리플렉션 없음  <  자체 검토만  <<  자체 검토 + 외부 피드백
```
코드 실행 결과, 웹 검색 사실 확인, 정규표현식 스캔, 단어 수 계산 —
**LLM이 못 하는 확인을 코드가 대신 해서 되먹인다.**

## 이 모듈의 한 문장

> **자체 검토만으로는 한계가 있다. 새 정보를 넣을 구멍을 찾아라.**

01번 레슨의 마지막 문장이자 06번 레슨의 결론이며,
그 구멍을 체계적으로 뚫는 방법이 다음 모듈의 **도구 사용(tool use)** 이다.

## 모듈 1과의 연결

| 모듈 1 | 모듈 2에서 심화된 부분 |
|---|---|
| [07. 디자인 패턴](../module-1-agentic-workflows/07-design-patterns.md)의 패턴 1 (리플렉션) | 모듈 2 전체 |
| [05. 작업 분해](../module-1-agentic-workflows/05-task-decomposition.md)의 4~5단계 (비평 → 수정) | 03, 06 |
| [06. 평가(evals)](../module-1-agentic-workflows/06-evals.md) | 05 — 객관/주관 구분, 루브릭 설계 |

직접 만든 [리서치 에이전트](../../projects/research-agent/README.md)에 이미 검토 단계(`critique` → `revise`)가 들어 있어, 이 모듈의 개념 대부분을 코드로 대조해볼 수 있었습니다. 각 노트 끝에 그 대조를 적어뒀습니다.

## 이미지

`images/` 안의 PNG 8장은 모두 **강의 슬라이드 캡처**입니다.
원본은 macOS 스크린샷(HEIC)이며, 마크다운에서 렌더링되지 않아 PNG로 변환해 저장했습니다.

| 파일 | 사용 위치 |
|---|---|
| `01-external-feedback.png` | 01 — 코드 실행 결과를 검토에 되먹이는 워크플로우 |
| `03-coffee-sales-data.png` | 03 — 커피 판매 CSV 원본 데이터 |
| `03-chart-agentic-workflow.png` | 03 — 차트 생성 워크플로우, plot.png → plot_v2.png |
| `05-sql-eval-dataset.png` | 05 — SQL 워크플로우와 정답 데이터셋, 87% vs 95% |
| `05-llm-as-judge-problems.png` | 05 — 쌍대비교 판정의 문제점 (위치 편향) |
| `05-rubric-grading.png` | 05 — 루브릭 기반 이진 채점 |
| `06-prompt-engineering-roi.png` | 06 — 노력 대비 성능 세 곡선 |
| `06-feedback-tool-examples.png` | 06 — 외부 피드백 소스 3종 표 |
