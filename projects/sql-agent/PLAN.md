# SQL 에이전트 — 기획서

> DeepLearning.AI *Agentic AI* 모듈 2 ungraded 랩
> "Improving SQL Generation with Reflection" 자체 구현.
> 작성 2026-08-05

## 1. 목적

랩이 명시한 학습 성과를 그대로 가져온다.

> *"You will practice applying the reflection pattern to improve an agentic
> workflow's ability to write SQL queries."*

**자연어 질문 → SQL → 실행 → 실행 결과를 보고 검토 → 개선된 SQL → 재실행.**

에이전트가 해야 할 네 가지도 랩이 정의한다.

| # | 랩이 요구하는 것 |
|---|---|
| 1 | 자기 중간 결과를 검토한다 (draft SQL, 도구 출력) |
| 2 | 오류와 누락을 식별한다 |
| 3 | 자기 응답과 도구 사용을 점검한다 |
| 4 | 최종 답을 내기 전에 수정한다 |

### 이 랩이 다루는 문제 — 문법으로 드러나지 않는 의미 오류

데이터가 **이벤트 로그**다. 한 행이 하나의 사건이고, 판매는 재고 유출이므로
`qty_delta` 가 음수로 기록된다. 이벤트 소싱에서 정상적인 모델링이다.

문제는 **그 의미가 스키마 타입에 드러나지 않는다**는 것이다. 모델이 보는 스키마는
`qty_delta (INTEGER)` 뿐이다. 그래서 이런 쿼리가 나온다.

```sql
SELECT color, SUM(qty_delta * unit_price) AS total_sales
FROM transactions WHERE action = 'sale' GROUP BY color
```

랩의 표현대로 *"technically valid but semantically incorrect"* 다.

랩 생성기는 `random.Random(42)` 로 결정적이라 결과가 재현된다. 실제로 돌려 확인했다.

| | 1위 | 값 |
|---|---|---|
| 부호를 무시하면 | blue | **−190,571.46** |
| 부호를 반영하면 | **white** | **358,315.09** |

**순위가 완전히 뒤집힌다.** 부호를 무시하면 "가장 덜 음수인" 색이 1위가 되므로,
정답에서 꼴찌인 blue 가 1위로 나온다. 값이 조금 틀리는 게 아니라 답이 반대가 된다.

> **−190,571.46 은 랩 문서의 값과 일치한다.** 재현 가능하다는 뜻이며, 필터 없는
> 같은 식은 −150,511.18 이므로 **V1 에 `WHERE action='sale'` 이 있었다**는 것도 알 수 있다.

**SQL 텍스트만 읽어서는 이 오류를 잡을 수 없다.** 스키마도 쿼리도 멀쩡하다.
실행해서 음수를 봐야 보인다 — 그것이 [06번 레슨](../../notes/module-2-reflection/06-using-external-feedback.md)의
**외부 피드백**이 필요한 이유이고, 이 랩의 존재 이유다.

### 랩이 제공하는 두 가지 검토 방식

| 절 | 함수 | 검토 재료 |
|---|---|---|
| 3.2.1 | `refine_sql` | SQL **텍스트만** |
| 3.2.2 | `refine_sql_external_feedback` | SQL + **실행 결과** |

랩은 전자가 이 오류를 놓치고 후자가 잡는다고 설명한다.
**우리는 그것을 수치로 확인한다** (§3 완료 기준 4).

## 2. 확보한 자료

| 항목 | 상태 |
|---|---|
| [노트북 `M2_UGL_2.md`](../../labs/module-2/sql/M2_UGL_2.md) | ✅ 프롬프트 3개 전문 포함 |
| [`utils.py`](../../labs/module-2/sql/utils.py) | ✅ 생성기 · 스키마 · 실행 함수 |
| [랩 `README.md`](../../labs/module-2/sql/README.md) | ✅ 이전 버전 기준이라 참고만 |
| 실행 출력 | ❌ 마크다운 내보내기라 출력 셀이 없다 |
| `products.db` | 받을 것이 아니다. `create_transactions_db()` 가 만든다 |

**실행 출력이 없다는 점이 설계에 영향을 준다.** 랩이 서술한 결과를 우리가 직접
본 적이 없으므로, 재현 여부를 **우리 판정기와 반복 실행으로** 확인한다 (§3, §6).

### 데이터 생성기는 결정적이다 — 그대로 재현한다

제품 100개 × 이벤트 50개, 비율 `restock 0.25 / sale 0.6 / price_update 0.15`.

**데이터가 정답을 결정한다.** 직접 만들면 정답 색상과 오차 크기가 달라져 랩이 적어둔
−190,571.46 과 대조할 수 없다. 생성기가 결정적이므로 그대로 재현하는 것이 옳다.

## 3. 완료 기준

| # | 기준 | 검증 |
|---|---|---|
| 1 | 질문 하나로 V1·V2 SQL과 두 결과가 나온다 | `python run.py "질문"` |
| 2 | 검토와 V2 SQL이 한 응답의 JSON에서 파싱된다 | `feedback` · `refined_sql` |
| 3 | 프롬프트 3개가 랩과 **축자로 일치**한다 | 자동 비교 테스트 (§5) |
| 4 | 검토 방식별 **성공률**을 낸다 | 아래 |
| 5 | 중간 산출물이 전부 보인다 | 스키마·V1·V1 결과·검토·V2·V2 결과 |
| 6 | 실행 실패가 조용히 넘어가지 않는다 | 명시적 플래그 |
| 7 | **모델을 바꿔 정확도를 비교한다** | 랩 Final Takeaways 4번 |

**4번이 대표 지표다.**

### 왜 단발 실행이 아니라 성공률인가

랩 §3.4 가 명시한다.

> *"Because Large Language Models (LLMs) are **stochastic**, every run may return
> slightly different results."*

단발 결과를 합격 조건으로 삼으면 **실패했을 때 우리 구현이 틀린 건지 모델이 흔들린
건지 구분할 수 없다.**

각 조건을 **N=10** 회 돌려 성공률을 낸다. **검증하는 것은 조건 간 방향성이지
특정 실행의 성패가 아니다.**

## 4. 범위

**A 없이 B를 하지 않는다.**

### A. 랩 재현 (필수)

- 5단계 워크플로우 — 스키마 → V1 → 실행 → 검토 → V2 → 실행
- `generate_sql` · `refine_sql` · `refine_sql_external_feedback` · `run_sql_workflow`
- JSON 파싱 + 실패 시 폴백
- 데이터셋 생성기 (랩과 같은 숫자를 내야 한다)
- SQLite 스키마 추출 · 쿼리 실행
- 단계별 산출물 표시·저장
- **정답 판정기** (§6.2) — 4·7번 기준의 토대
- **N회 반복 실행과 성공률 집계** — 완료 기준 4
- **모델 조합 실험** — 완료 기준 7

> **모델 실험은 랩이 명시한 학습 성과다.** Final Takeaways 4번 —
> *"Experiment with different LLM models to compare performance and **accuracy**."*
> 랩 §3.4 가 `gpt-4o` · `gpt-4.1` · `gpt-4.1-mini` · `gpt-3.5-turbo` 를 나열한다.
>
> 정답 판정기(§6.2)가 있으므로 랩이 말한 *accuracy* 를 문자 그대로 잴 수 있다 —
> **모델 × 조건별 성공률 표.**

### B. 확장 (A 완료 후)

| # | 확장 | 근거 |
|---|---|---|
| B1 | **정답 데이터셋 기반 정확도 측정** | [05번 레슨](../../notes/module-2-reflection/05-evaluating-reflection.md)의 87%→95% |
| B2 | SQL 실행 오류를 명시적으로 되먹임 | [01·06번 레슨](../../notes/module-2-reflection/01-reflection-basics.md) · §5.6 |

완료 기준 4번이 질문 **1개** × 조건 × N회라면, B1 은 질문 **여러 개** × 조건 × N회다.
같은 판정기와 집계 코드를 쓴다.

### 제외

| 항목 | 이유 |
|---|---|
| 노트북 HTML 렌더링 | CLI 콘솔 + 파일로 대체 |
| 프레임워크 | [CLAUDE.md](../../CLAUDE.md) 하드 제약 |
| SQL 실행 샌드박싱 | 읽기 전용 로컬 SQLite. §7 참고 |
| 프롬프트 개선 | A 는 축자 재현이 목적이다 |

## 5. 랩 명세

**프롬프트는 축자로 재현한다.** 모델 입력이므로 한 글자도 바꾸지 않고, 공백·들여쓰기까지
자동 비교 테스트로 고정한다 (완료 기준 3).

아래 세 블록은 **모델이 실제로 받는 문자열**이다 — 노트북 소스가 아니다.
⚠ `refine_sql` 소스의 `{{` / `}}` 는 f-string 이스케이프이므로 모델에게는 `{` / `}` 로
간다. **비교 테스트는 f-string 을 렌더한 뒤 대조해야 한다.** 소스끼리 비교하면
그 두 줄에서 헛되이 실패한다.

세 프롬프트 모두 노트북과 축자 일치함을 확인했다.

### 5.1. `generate_sql(question, schema, model) -> str`

f-string 안의 **4칸 들여쓰기가 프롬프트에 그대로 들어간다.**

```
    You are a SQL assistant. Given the schema and the user's question, write a SQL query for SQLite.

    Schema:
    {schema}

    User question:
    {question}

    Respond with the SQL only.
```

`temperature=0` · 반환은 `.strip()` 만 한 원문.

### 5.2. `refine_sql(question, sql_query, schema, model) -> (feedback, refined_sql)`

**실행하지 않는다.** SQL 텍스트만 검토한다. **이 프롬프트만 들여쓰기가 없다.**

```
You are a SQL reviewer and refiner.

User asked:
{question}

Original SQL:
{sql_query}

Table Schema:
{schema}

Step 1: Briefly evaluate if the SQL OUTPUT fully answers the user's question.
Step 2: If improvement is needed, provide a refined SQL query for SQLite.
If the original SQL is already correct, return it unchanged.

Return STRICT JSON with two fields:
{
  "feedback": "<1-3 sentences explaining the gap or confirming correctness>",
  "refined_sql": "<final SQL to run>"
}
```

`temperature=0`.

> 이 프롬프트는 *"the SQL OUTPUT"* 을 평가하라고 하면서 출력을 전달하지 않는다.
> **이것이 3.2.1 의 성격이다** — 모델은 실행 결과 없이 판단해야 한다. 축자로 재현한다.

### 5.3. `refine_sql_external_feedback(question, sql_query, df_feedback, schema, model)`

```
    You are a SQL reviewer and refiner.

    User asked:
    {question}

    Original SQL:
    {sql_query}

    SQL Output:
    {df_feedback.to_markdown(index=False)}

    Table Schema:
    {schema}

    Step 1: Briefly evaluate if the SQL output answers the user's question.
    Step 2: If the SQL could be improved, provide a refined SQL query.
    If the original SQL is already correct, return it unchanged.

    Return a strict JSON object with two fields:
    - "feedback": brief evaluation and suggestions
    - "refined_sql": the final SQL to run
```

`temperature=1.0`.

### 5.4. 두 검토 함수는 실행 결과 외에도 다르다 → 통제 조건을 추가한다

두 프롬프트를 나란히 놓으면 차이가 여섯 군데다.

| # | `refine_sql` | `refine_sql_external_feedback` |
|---|---|---|
| 1 | — | **`SQL Output:` 블록** |
| 2 | `temperature=0` | **`temperature=1.0`** |
| 3 | 들여쓰기 없음 | 4칸 들여쓰기 |
| 4 | *"the SQL **OUTPUT** **fully** answers"* | *"the SQL output answers"* |
| 5 | *"a refined SQL query **for SQLite**"* | *"a refined SQL query"* |
| 6 | `Return STRICT JSON` + JSON 리터럴 | `Return a strict JSON object` + 불릿 |

**2번이 결과 해석에 직접 영향을 준다.** 외부 피드백 쪽 성공률이 높게 나와도
실행 결과 덕분인지 temperature 덕분인지 구분할 수 없다.

**우리 프로세스에서는 네 번째 조건을 추가해 이 변인을 분리한다.**

| 조건 | 검토 함수 | temperature |
|---|---|---|
| `none` | 검토 없음 | — |
| `text` | `refine_sql` | 0 |
| `feedback` | `refine_sql_external_feedback` | 1.0 (랩 그대로) |
| **`feedback-t0`** | `refine_sql_external_feedback` | **0** ← 우리가 추가 |

`text` 와 `feedback-t0` 을 비교하면 **temperature 가 같으므로 실행 결과의 효과만
남는다.** 프롬프트는 랩 그대로 두고 호출 인자만 바꾸므로 축자 재현을 깨지 않는다.

### 5.5. 스키마 — 모델에게는 컬럼명과 타입만 간다

```
table name: transactions
id (INTEGER)           ← 사실상 유일한 순서 정보
product_id (INTEGER)
product_name (TEXT)
brand (TEXT)
category (TEXT)
color (TEXT)
action (TEXT)          ← 값이 4종이라는 정보는 없다
qty_delta (INTEGER)    ← 부호 규칙은 없다
unit_price (REAL)      ← restock 에서 NULL 이라는 정보는 없다
notes (TEXT)
ts (DATETIME)
```

**이것이 과제의 성격이다.** 의미 규칙이 스키마에 없으므로 모델은 실행해봐야 안다.
스키마를 보강하면 문제 자체가 사라진다 — 하지 않는다.

랩은 3.1·3.2 에서 하드코딩 문자열을, 3.3 에서 `get_schema()` 를 쓴다. 대소문자만
다르고 컬럼 목록은 동일하다 — 확인했다. **우리는 `get_schema()` 한 곳으로 통일한다.**

### 5.6. `execute_sql` — 오류가 곧 외부 피드백이 된다

```python
try:
    return pd.read_sql_query(q, conn)
except Exception as e:
    return pd.DataFrame({"error": [str(e)]})
```

SQL 오류 메시지가 한 행짜리 DataFrame 이 되어 `to_markdown()` 을 거쳐 검토 프롬프트로
들어간다. **실행 오류 되먹임이 이미 절반 구현돼 있는 셈**이므로 이 동작을 유지한다.

**우리가 더하는 것:** 오류 여부를 별도 플래그로 돌려준다. 그러지 않으면 `error` 컬럼
한 줄이 "최종 답" 으로 표시되고, 판정기가 성공으로 셀 수 있다 (§6.2 규칙 1).

마크다운 펜스도 여기서 벗긴다 — `removeprefix("```sql")` / `removesuffix("```")`.

### 5.7. `run_sql_workflow`

5단계를 순서대로 돌리고 각 단계를 표시한다. **랩은 반환값이 없다.**
우리는 산출물 dict 를 돌려준다 — 저장·판정·집계에 필요하다.

### 5.8. 강의 슬라이드는 LLM 호출 3번, 랩은 2번

강의의 반성 워크플로우는 시도 / 검토 / 수정을 **세 호출**로 나눈다.
**모듈 2의 두 랩은 모두 검토와 수정을 한 호출로 합쳤다** — 그래서
`{"feedback", "refined_sql"}` JSON 파싱이 필요해진다.

**랩대로 2번으로 간다.** JSON 파싱이 학습 포인트이고, 조건 간 비교가 성립하려면
검토 함수들의 구조가 같아야 한다. 호출을 셋으로 나누는 실험은 이 랩의 범위 밖이다.

## 6. 평가 설계

### 6.1. 정답 데이터셋

우리가 데이터를 만드므로 정답 SQL 을 손으로 쓸 수 있다. 비교는 **값**으로 한다 —
같은 답을 내는 SQL 은 여러 가지다.

**질문 세트 — 전부 실제로 돌려 정답이 존재함을 확인했다.**
질문 문장과 정답은 [`invariants.py`](sql_agent/invariants.py) 의 `EXPECTATIONS` 가 원본이고,
아래 표는 그 사본이다. 채점기(§6.2)와 평가 세트도 같은 곳을 읽는다.


| 유형 | 질문 | 정답 | 요구하는 것 |
|---|---|---|---|
| 부호 | *"Which color of product has the highest total sales? Consider sale events only."* | white / 358,315.09 | `qty_delta < 0` 인지 |
| 부호 | *"Which brand generated the most sales revenue? Consider sale events only."* | Nike / 384,355.53 | 같음, 그룹만 다름 |
| 순서 | *"What is the current price of product 1?"* | 57.16 | 마지막 가격 이벤트를 `id` 로 찾는다 |
| 상태 재구성 | *"Which product has the highest current stock?"* | 34번 / 197 | `SUM(qty_delta)` — 여기서는 부호가 맞다 |
| 단순 집계 | *"How many sale events are there?"* | 2,919 | 대조군 |
| 단순 집계 | *"How many units were restocked in total?"* | 16,753 | 대조군 |

**질문 설계 제약 두 가지 — 데이터를 확인해서 알아낸 것이다.**

1. **시간 조건을 쓸 수 없다.** `ts` 는 `CURRENT_TIMESTAMP` 기본값이라 5,000행이
   전부 DB 를 만든 그 몇 초 안에 들어간다. 어떤 날짜 필터도 전부이거나 0행이다.
   순서가 필요하면 `id` 를 쓴다. 랩의 예제 질문도 시간과 무관하므로 재현에는 지장이 없다.
2. **`restock` 의 금액을 물을 수 없다.** `unit_price` 가 1,258행 전부 NULL 이라
   `SUM(qty_delta * unit_price)` 가 NULL 이 된다. 금액 대신 수량을 묻는다.

> **평가 질문은 반드시 먼저 실행해보고 넣는다.** 초안에서 *"2025년 5월에 몇 개
> 팔렸나?"* 를 검증 없이 넣었다가 0행임을 뒤늦게 발견했다.

⚠ **질문이 모호하면 정확도가 모델 능력이 아니라 우리 질문의 품질을 잰다.**
"총 매출" 하나만 해도 `sale` 행만 셀지 갈린다. 대응:

1. 질문에 해석을 못박는다 — *"Consider sale events only."*
2. 그래도 갈리면 정답을 **허용 집합**으로 둔다
3. 오답을 **해석 차이 / 실제 오류**로 분류한다

**집계는 두 벌로 낸다.** 전체 평균만 보면 대조군이 차이를 희석시킨다.

| 집계 | 용도 |
|---|---|
| 전체 평균 | 05번 레슨의 87%↔95% 와 형태를 맞춘 숫자 |
| **부호·순서 질문만** | 검토의 효과가 실제로 드러나는 곳 |

대조군은 **검토가 맞는 답을 망가뜨리지 않는지** 확인하는 용도다.

### 6.2. "정답 도달" 의 판정 규칙

완료 기준 4·7의 성공률을 세려면 **성공의 정의**가 필요하다. 없으면 구현할 수 없다.

| # | 규칙 |
|---|---|
| 1 | 결과가 **오류 DataFrame 이 아닐 것** (`error` 컬럼 없음 — §5.6) |
| 2 | 행이 1개 이상일 것 |
| 3 | **첫 행**의 그룹 키가 정답과 일치할 것 |
| 4 | 첫 행의 값이 정답의 **±0.01** 이내일 것 |

3번이 "첫 행" 인 이유 — *"가장 높은 …은?"* 에 모델은 `LIMIT 1` 을 붙이기도 하고
전체를 `ORDER BY` 로 정렬해 주기도 한다. 둘 다 인정하되 **정렬은 요구한다.**
정렬 없이 5행을 주면 답을 고른 것이 아니다.

4번의 ±0.01 은 부동소수점·반올림 차이만 흡수한다.
`SUM(ABS(qty_delta)*unit_price)` 와 `SUM(-qty_delta*unit_price)` 는 같은 값이므로
**SQL 문자열은 보지 않는다.**

### 6.3. 조건 설계

| 조건 | 검토 | 06번 레슨 대응 |
|---|---|---|
| `none` | 없음 | 🔴 빨간 곡선 |
| `text` | `refine_sql` | 🔵 파란 곡선 |
| `feedback` | `refine_sql_external_feedback` (랩 그대로) | 🟡 노란 곡선 |
| `feedback-t0` | 위 + `temperature=0` | 우리가 추가한 통제 조건 (§5.4) |

⚠ **반복의 의미가 조건마다 다르다.** `none` 과 `text` 는 `temperature=0` 이라
거의 결정적이고, `feedback` 만 실질적으로 변동한다.
[ESTIMATE] OpenAI 는 `temperature=0` 에서도 완전 결정적이지 않으므로 그래도 돌리되,
**분산이 조건마다 다르게 나올 것을 예상하고 해석한다.** `feedback-t0` 이 이 해석을
가능하게 한다.

## 7. 설계 결정

| 결정 | 선택 | 근거 |
|---|---|---|
| 실행 형태 | CLI 모듈 | 반복 실행과 결과 비교에 필요 |
| LLM 호출 | **aisuite** | 랩이 `ai.Client()` 를 쓴다. 이미지가 없어 충분 |
| DB | SQLite (`products.db`) | 랩과 동일 |
| 데이터 생성 | **랩 생성기를 충실히 재현** | 데이터가 정답을 결정한다 (§2) |
| 스키마 출처 | `get_schema()` 한 곳 | §5.5 |
| SQL 실행 | 읽기 전용 연결 | 아래 |
| 프롬프트 | **축자 재현 + 자동 비교 테스트** | 모델 입력이다 |
| 조건 | 랩의 3개 + **통제 조건 1개** | §5.4 |
| 반복 실행 | **N=10 기본** | §3 |
| 반복 산출물 | `runs/{시각}_{라벨}/{조건}/{회차}/` | 40개 실행이 섞이지 않게 |
| 생성/평가 모델 | `openai:gpt-4.1` 기본 | 랩 기본값. 완료 기준 7에서 바꿔본다 |

### 리스크

| 리스크 | 대응 |
|---|---|
| **LLM 이 쓴 SQL 실행** | 읽기 전용 연결(`file:…?mode=ro`)로 `DROP`·`UPDATE` 차단. ⚠ 파일 수준 보호이지 완전한 격리는 아니다 |
| 단발 결과로 판정 | N회 반복 + 성공률 (§3) |
| 변인이 섞인 조건 비교 | `feedback-t0` 통제 조건 (§5.4) |
| 평가 질문의 모호성 | 해석 명시 + 허용 집합 + 오답 분류 (§6.1) |
| JSON 파싱 실패 | 랩과 같은 폴백. **파싱 실패 사실은 별도 기록** |
| API 비용 | 1회 = 텍스트 1~2회 호출. N × 조건 × 질문 × 모델로 곱해진다 |

### 코드 재사용

`config.py` · `llm.py` (텍스트) · `trace.py` · `report.py` · `runs/` 규약은 기존
프로젝트에서 **복사해 쓴다.** 지금 공통 모듈로 뽑으면 추측이 되므로, 동작하는 것을
만든 뒤 실제로 무엇이 같았는지 보고 결정한다.

`executor.py` 는 새로 쓴다 — SQL 실행이라 성격이 다르다.

## 8. 비목표

- SQL 인젝션 방어 · 프로덕션 DB 접근
- 노트북 UI 재현
- 여러 테이블·조인 — 랩은 단일 테이블이다
- 스키마에 의미 규칙 보강 — 문제 자체가 사라진다 (§5.5)
- 공통 모듈 추출 — §7

## 9. 완성 후

1. **조건별 성공률** — `none` / `text` / `feedback` / `feedback-t0`
2. **모델별 정확도** — 완료 기준 7
3. **B1 정답 데이터셋** — 05번 레슨의 87%↔95% 에 해당하는 숫자
4. **공통 모듈 추출 판단** — 실제로 무엇이 같았는지 보고
5. 회고를 `notes/retrospectives/` 에 기록
