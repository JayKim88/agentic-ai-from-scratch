# 회고 — 자체 구현 리서치 에이전트 vs. 공식 저장소

> 작성 2026-08-03 · 대상: [projects/research-agent](../../projects/research-agent/README.md) ↔
> [https-deeplearning-ai/agentic-ai-public](https://github.com/https-deeplearning-ai/agentic-ai-public)
>
> [CHECKLIST 규칙 1](../../projects/research-agent/CHECKLIST.md) — *"완성 전까지 공식 저장소를 열지 않는다"* —
> 을 지켜 자체 구현을 끝낸 뒤에 대조했다.

## 한 줄 요약

**공식 저장소는 자료 수집의 깊이와 자율성에서 앞서고, 우리 구현은 평가·추적·인용 검증에서 앞선다.**
가장 뜻밖의 발견은 공식 구현이 **강의가 가르친 반성 분해를 오히려 합쳐놓았다**는 점이다.

---

## 1. 정면 대조

| 항목 | 공식 저장소 | 우리 구현 |
|---|---|---|
| 규모 | 1,107줄 (`src/` 3개 + `main.py`) | 1,424줄 (8개 모듈) |
| 단계 결정 | **LLM 플래너가 런타임에 생성** (최대 7단계) | 하드코딩 7단계 |
| 도구 호출 루프 | aisuite `max_turns=5` **위임** | **직접 구현** |
| 도구 | Tavily, arXiv(**PDF 본문**), Wikipedia | Tavily, arXiv(초록), Wikipedia |
| 반성 | editor가 비평+수정을 **한 번에** | 비평/수정 **분리** (2단계) |
| 인용 검증 | 프롬프트 지시만 | **번호 소스 목록 주입 + eval 검증** |
| 평가 | **없음** | 객관적 8종 |
| 추적 | stdout `print` + HTML 문자열 | **구조화 JSON** (프롬프트·출력·시간) |
| 인터페이스 | FastAPI + Postgres + 웹 UI | CLI |

---

## 2. 공식 저장소가 나은 점 — 가져올 것

### ① arXiv PDF 본문 추출 (가장 큰 격차)

`research_tools.py:160-166`에서 초록이 아니라 **PDF 본문**을 긁는다.

```python
_INCLUDE_PDF = True
_EXTRACT_TEXT = True
_MAX_PAGES = 6
_TEXT_CHARS = 5000
```

`summary` 필드를 PDF에서 뽑은 텍스트로 **덮어쓴다**. 우리는 초록(수백 자)만 쓰므로
학술 주제에서 근거의 깊이가 확실히 뒤진다.

> 반영 가치 **높음.** 다만 `pdfminer.six`/`pymupdf`가 코스 requirements에 없어
> 별도 설치가 필요하다 — [PLAN.md](../../projects/research-agent/PLAN.md)에서 범위 밖으로 뒀던 항목.

### ② 동적 플래너

`planner_agent()`가 주제를 보고 단계 목록을 **런타임에 생성**한다. 우리는 7단계 고정이다.
다만 무조건 우월한 것은 아니다 — `_ensure_contract()`로 1·2번째와 마지막 단계를
강제로 덮어쓰고 있어, 실제 자유도는 가운데 3~4단계뿐이다.
자율성을 준 뒤 다시 규칙으로 묶는 구조는 그 자체로 흥미로운 절충안이다.

> 반영 가치 **보류.** 단계 순서를 LLM이 정하는 것은 모듈 5(Planning)의 주제다.
> 지금 넣으면 모듈 1의 범위를 넘는다.

### ③ 실행 히스토리를 유형별로 태깅해 전달

`executor_agent_step()`은 이전 단계 출력을 `✍️ Draft` / `🧠 Feedback` / `🔍 Research`로
분류해 컨텍스트를 만든다. 우리는 단계별로 필요한 것만 골라 넘긴다.
공식 방식이 정보 손실은 적지만 프롬프트가 더 빨리 커진다.

### ④ Writer 프롬프트의 구조 강제

Abstract / Introduction / Background / Methodology / Findings / Discussion /
Conclusion / References — **9개 섹션을 필수로 못박고** 1,500~3,000 단어를 요구한다.
프롬프트 안에 내부 체크리스트까지 넣었다. 우리 프롬프트는 훨씬 가볍다.

> 반영 가치 **중간.** 학술 리포트에는 맞지만 모든 주제에 9개 섹션이 적합하진 않다.

---

## 3. 우리 구현이 나은 점

### ① 평가가 존재한다 (공식은 0)

`src/`와 `main.py` 전체를 검색해도 eval·metric·검증 코드가 **하나도 없다.**
리포트 품질을 판정할 방법이 없다.

이것은 단순한 기능 차이가 아니다. [모듈 1 레슨 6](../module-1-agentic-workflows/06-evals.md)이
*"에이전틱 워크플로우를 잘 만드는지를 가장 크게 예측하는 요인은 체계적인 평가 프로세스"* 라고
가르쳤는데, **공식 데모는 그 가르침을 구현하지 않았다.**
데모 앱과 학습 목적의 차이로 이해할 수 있지만, 짚어둘 만하다.

### ② 인용 정합성을 강제하는 메커니즘

| | 공식 | 우리 |
|---|---|---|
| 방법 | 프롬프트에 *"Preserve ALL original URLs"* 지시 | 번호 매긴 소스 목록 주입 + *"목록에서만 인용"* |
| 검증 | 없음 | `collected_urls()`와 대조하는 eval |

우리 실행에서 **인용 21/21 전부 근거 있음**이 자동 판정됐다.
공식 구현은 같은 상황에서 환각이 생겨도 알 방법이 없다.

### ③ 비평과 수정의 분리

공식 `editor_agent`의 지시는 *"Return only the revised, polished text"* — **비평과 수정을 한 번에** 한다.
우리는 분리했고, 프롬프트에 명시적으로 `"Do NOT rewrite it. List concrete problems only"`를 넣었다.

[05번 노트](../module-1-agentic-workflows/05-task-decomposition.md)에서 강의가
"에세이 작성"을 초안 → **수정할 부분 파악** → 수정 셋으로 쪼개 품질을 올렸다고 가르쳤는데,
**공식 구현은 그 분해를 되돌려놓았다.**

우리 실행에서 분리의 효과가 측정됐다: 비평이 16개 항목을 지적했고,
수정 단계가 `70-80% of its components` → `many`,
`flew over 160 launches in 2025` → `has increased launch rates significantly` 처럼
**근거 없는 구체 수치를 스스로 삭제**했다.

### ④ 구조화된 트레이스

공식은 `print()`와 HTML 문자열로 남긴다. 우리는 단계별 프롬프트·출력·도구 호출·소요 시간을
JSON으로 저장한다. 덕분에 데이터 흐름 매트릭스 같은 사후 분석이 가능했다.

---

## 4. 공식 저장소에서 발견한 결함

데모 코드임을 감안해도 짚을 만한 것들이다. **동작 참조로는 훌륭하지만 코드 품질 참조로는 부적합하다.**

### ① 단계 라우팅이 문자열 매칭 — 실제 오작동 재현됨

`executor_agent_step()`은 단계 제목의 키워드로 에이전트를 고른다.

```python
if "research" in step_lower:     ...
elif "draft" in step_lower or "write" in step_lower: ...
elif "revise" in step_lower or "edit" in step_lower or "feedback" in step_lower: ...
else: raise ValueError(f"Unknown step type: {step_title}")
```

플래너가 만드는 단계 제목은 `"Editor agent: ..."` 처럼 **담당 에이전트를 명시**하는데,
라우팅은 그 접두사를 무시하고 본문 키워드를 먼저 본다. 재현 결과:

| 플래너가 만든 단계 | 의도 | 실제 라우팅 |
|---|---|---|
| `Editor agent: Review the research findings for coherence.` | editor | **research** ❌ |
| `Editor agent: Provide feedback on the research draft.` | editor | **research** ❌ |
| `Analyst agent: Rank and deduplicate the collected items.` | — | **ValueError** ❌ |

플래너는 LLM이고 중간 단계 제목은 자유 서술이므로, `"research"`라는 단어가 섞이는 순간
편집 단계가 리서치 에이전트로 간다. 세 번째 경우는 예외가 나서 워크플로우 전체가 중단된다
(`main.py`가 잡아 task를 error로 기록).

### ② 조용한 에러 처리

```python
except Exception as e:
    print("❌ Error:", e)
    return f"[Model Error: {str(e)}]", messages
```

에러가 **리포트 본문에 들어갈 문자열로 변환**된다. 호출부는 정상 출력과 구별할 수 없다.
`agents.py`의 도구 호출 수집부에는 `except Exception: pass`도 있다.

### ③ 사용되지 않는 파라미터

`writer_agent(min_words_total=2400, min_words_per_section=400, retries=1)` —
셋 다 함수 본문에서 **한 번도 쓰이지 않는다.** `_word_count()`도 정의만 되고 호출되지 않는다.
분량 강제가 의도됐다가 미완으로 남은 흔적으로 보인다.

### ④ 코드 위생

- `from urllib import response` — 미사용 import
- `from typing import List` 중복 (3행, 23행)
- 스페인어 주석 혼재 (`# Construir contexto enriquecido`, `# ⚠️ NO <pre> AQUÍ`)
- `import json as _json`을 루프 안에서 수행
- `arxiv_search_tool`의 docstring이 **스페인어** → 이 문장이 그대로 모델에게 전달된다

마지막 항목은 특히 아이러니하다. **docstring이 곧 인터페이스**인데,
Tavily·Wikipedia 도구는 영어 Google 스타일로 잘 쓰여 있는 반면
arXiv 도구만 스페인어 서술형이라 모델이 받는 설명의 품질이 도구마다 들쭉날쭉하다.

---

## 5. 강의 대비 관찰

| 강의가 가르친 것 | 공식 구현 | 우리 구현 |
|---|---|---|
| 반성 = 초안/파악/수정 3단계 분해 | 합쳐놓음 (1단계) | 분리 ✅ |
| 평가가 성패를 가르는 요인 | 없음 | 8종 ✅ |
| 중간 출력(트레이스) 검토가 핵심 스킬 | print/HTML | 구조화 JSON ✅ |
| 도구는 함수 + docstring | ✅ (aisuite 자동) | ✅ (직접 구현) |
| 자율성 스펙트럼 | 높음 (플래너) | 반자율 |

**강의 내용을 가장 충실히 따른 쪽은 오히려 우리 구현이다.**
공식 저장소는 "동작하는 데모"가 목표였고, 우리는 "강의 개념의 구현"이 목표였으므로
당연한 결과이기도 하다.

---

## 6. 반영할 것

| 우선순위 | 항목 | 근거 |
|---|---|---|
| **높음** | arXiv PDF 본문 추출 | 학술 주제에서 근거 깊이가 명확히 부족 |
| 중간 | 2단계 원본 스니펫을 뒤 단계로 전달 | 현재 모델 요약만 전달돼 정보 손실 (5단계 검증에서 관찰) |
| 중간 | Writer 프롬프트에 섹션 구조 강제 옵션 | 주제 유형에 따라 선택적으로 |
| 낮음 | 동적 플래너 | 모듈 5 주제 — 그때 확장 |

**하지 않을 것:** FastAPI·Postgres·웹 UI. [PLAN.md](../../projects/research-agent/PLAN.md)에서
에이전틱 로직과 무관한 인프라로 분류한 판단을 유지한다. 대조 후에도 이 판단은 바뀌지 않았다.

---

## 7. 이 방식(먼저 만들고 나중에 대조)에 대한 평가

정답을 먼저 봤다면 얻지 못했을 것들:

1. **라우팅 결함을 발견할 수 없었을 것이다.** 직접 라우팅을 고민해본 적이 없으면
   `if "research" in step_lower`가 문제로 보이지 않는다.
2. **평가의 부재를 이상하게 여기지 않았을 것이다.** eval을 직접 만들어 6/8 → 8/8을
   겪었기에 "왜 없지?"가 눈에 띈다.
3. **비평/수정 분리의 값을 몰랐을 것이다.** 분리했더니 모델이 자기 환각을 삭제하는 걸
   관찰했기 때문에, 공식이 합쳐놓은 것이 후퇴로 보인다.

반대로 대조하지 않았다면 **PDF 본문 추출**이라는 명확한 개선점을 놓쳤을 것이다.
순서가 중요했다: 먼저 만들고, 평가하고, 그다음 대조.
