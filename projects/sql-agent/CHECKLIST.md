# 작업 체크리스트

> 기획서: [PLAN.md](PLAN.md) · 최종 수정 2026-08-05

**A(1~5단계)가 랩 재현, B(6단계)가 확장. A 없이 B를 하지 않는다.**

| 단계 | 구분 | 상태 |
|---|---|---|
| 0. 준비 | — | 🔄 |
| 1. 데이터 계층 (SQLite) | A | ✅ |
| 2. 실행 계층 (쿼리 실행) | A | ✅ |
| 3. LLM 계층 (프롬프트 3개) | A | ✅ |
| 4. 워크플로우와 판정기 | A | ✅ |
| 5. 재현 검증 · 성공률 · 모델 비교 | A | ⬜ |
| 6. 확장 (B1·B2) | B | ⬜ |
| 7. 회고 | — | ⬜ |

---

## 0. 준비

- [x] `PLAN.md` · 이 문서 작성
- [x] `OPENAI_API_KEY` 확인
- [x] 랩 자료를 [`labs/module-2/sql/`](../../labs/module-2/sql/) 로 —
      [`M2_UGL_2.md`](../../labs/module-2/sql/M2_UGL_2.md) · `utils.py` · 랩 `README.md`
- [x] `to_markdown` 에 필요한 `tabulate` — 이미 설치·기록돼 있다
- [x] `.gitignore` 에 `products.db` 추가 (생성물이고 결정적이라 커밋 불필요)
- [ ] 재사용할 모듈 결정 — **복사한다** ([PLAN §7](PLAN.md))

## 1. 데이터 계층 [A]

**데이터가 정답을 결정한다.** 생성기가 `random.Random(42)` 로 결정적이므로
**충실히 재현**한다. 직접 만들면 정답값이 달라져 랩과 대조할 수 없다.

- [x] `sql_agent/dataset.py` — 랩 `create_transactions_db` 재현
  - [x] 11컬럼 · 시드 `42` · 제품 100 × 이벤트 50 · 비율 `.25 / .6 / .15`
  - [x] `action` 4종 — `insert` 는 개시 재고, `sale` 은 **그 시점 `current_price`**
  - [x] `qty_delta` 부호 — `insert`/`restock` +, `sale` **−**, `price_update` 0
  - [x] `unit_price` 는 `restock` 에서만 NULL
  - [x] `ts` 는 랩과 동일하게 `DEFAULT CURRENT_TIMESTAMP` 에 맡긴다
  - [x] **`brand`/`category` 를 `product_name.split()` 으로 뽑는다** —
        "New Balance" 제품이 brand `New` · category `Balance` 가 된다.
        고치면 데이터가 달라지므로 그대로 재현
- [x] `get_schema(db_path)` — `PRAGMA table_info` 기반, 한 곳으로 통일 ([PLAN §5.5](PLAN.md))
  - [x] 랩 `get_schema` 와 문자열까지 일치 확인
- [x] `ensure_database()` — 없을 때만 생성

### 랩과 같은 데이터인지 확인 — 회귀 테스트로 고정

- [x] 기획 단계에서 확인함 ([PLAN §1](PLAN.md))
  - [x] `SUM(qty_delta * unit_price)` + `WHERE action='sale'` → **−190,571.46** (blue)
  - [x] `SUM(ABS(qty_delta) * unit_price)` → **+358,315.09** (white)
  - [x] 1위가 **blue → white** 로 뒤집힌다
- [x] `sql_agent/invariants.py` — 위 값들을 **고정하고 검사한다**
  - [x] 행 수 · action 별 건수 · `restock` 의 `unit_price` 전부 NULL
  - [x] `ts` 가 **생성 시각 몇 초 안**에 들어간다 — distinct 개수가 아니라 **폭**으로 검사한다.
        `CURRENT_TIMESTAMP` 는 1초 해상도라 초 경계를 넘으면 distinct 가 2가 된다
  - [x] 부호 역전 (`blue` → `white`) 과 필터 없는 값 **−150,511.18**
  - [x] 평가 질문 6개 — **모델이 받을 문장 그대로** `EXPECTATIONS` 에 보관.
        채점기와 평가 세트가 같은 곳을 읽어 문구가 갈라지지 않게 한다
  - [x] **랩 생성기와 전 행 대조** — `compare_with_lab_generator()`
- [x] **10컬럼 × 5,000행 완전 일치 확인** (`ts` 는 생성 시각이라 제외)
- [x] 검사가 실제로 실패를 잡는지 확인 — 시드·비율·제품수 변경, `notes` 한 줄 변경,
      테이블 없는 DB 모두 검출됨. **`notes` 변경은 값 불변식을 통과하므로 행 대조가 필요하다**

```bash
python -m sql_agent.invariants
```

> 이 숫자들이 재현되지 않으면 랩과 다른 데이터를 만든 것이다. **먼저 이것부터 확인**한다.

## 2. 실행 계층 [A]

- [x] `sql_agent/executor.py` — `run_query(sql, db_path) -> QueryResult`
      (기획서에는 `execute_sql(...) -> DataFrame` 로 적었으나, DataFrame 하나로는
      오류 여부를 실어보낼 수 없어 이름과 반환형을 바꿨다. **프레임 자체는 랩과 동일**)
  - [x] **읽기 전용 연결** (`file:…?mode=ro&uri=true`)
  - [x] 마크다운 펜스 제거 — 랩과 동일하게 `` ```sql `` 접두 / `` ``` `` 접미만.
        더 느슨하게 벗기면 랩에서 실패할 쿼리가 살아나 **성공률이 모델이 아니라
        우리 정규화를 재게 된다**
  - [x] **오류를 `DataFrame({"error": [...]})` 로 바꾸는 동작 유지** —
        그것이 곧 외부 피드백이 된다 ([PLAN §5.6](PLAN.md))
  - [x] **`has_error` 플래그** — 판정기가 오류 프레임을 성공으로 세지 않게
  - [x] **쿼리 타임아웃** — 랩에 없다. 배치 실행에서 카티션 조인 하나가
        수백 개 쿼리를 멈춰세우지 않도록. 타임아웃도 오류 프레임으로 나가 피드백이 된다
- [x] **랩 `execute_sql` 과 출력 대조** — 7개 케이스에서 프레임·마크다운 모두 동일
      (정상 집계 · 펜스 · 문법 오류 · 없는 컬럼 · 없는 테이블 · 펜스에 sql 없음 · 0행)
- [x] 일부러 깨지는 SQL 검증 — 오류 메시지가 그대로 피드백에 실린다
- [x] `DROP TABLE` · `UPDATE` 가 읽기 전용에서 막히고, 이후 불변식이 그대로인지 확인
- [x] 타임아웃 오탐 검사 — `SELECT 'interrupted'` 는 정상 처리된다
- [x] **DB 경로에 `?` `#` 공백이 있어도 동작** — URI 를 f-string 으로 만들면
      경로가 query/fragment 로 잘려 엉뚱한 파일이 열리고, 그 "no such table" 이
      **모델의 실수처럼 보인다.** `Path.as_uri()` 로 인코딩한다

> ⚠ **의도적 차이 하나.** 랩은 읽기·쓰기 연결이라 `DROP TABLE` 이 **실제로 실행된다.**
> 우리는 막고 오류 프레임을 돌려주므로, 쓰기 쿼리에서만 모델이 보는 피드백이 달라진다.
> 측정 기준 DB 를 지키는 쪽이 우선이다.

## 3. LLM 계층 [A]

- [x] `sql_agent/config.py` — 모델 기본값(`openai:gpt-4.1`), 키 검증, **온도 상수**
  - [x] 랩 값 그대로: 생성 0 · 텍스트 검토 0 · 외부 피드백 1.0
  - [x] `CONTROLLED_FEEDBACK_TEMPERATURE` — 통제 조건용 ([PLAN §5.4](PLAN.md))
- [x] `sql_agent/llm.py` — aisuite 텍스트 호출.
      **`temperature` 를 기본값 없는 필수 인자로** — 조건을 가르는 값이라 암묵적으로 두면
      비교가 아무도 안 본 기본값에 의존하게 된다
- [x] `sql_agent/sqlgen.py` — 프롬프트 3개를 **축자로**
  - [x] `generate_sql` · `refine_sql` · `refine_sql_external_feedback` — 랩과 같은 이름
  - [x] **앞 개행과 뒤 들여쓰기까지 포함**해 재현. 그것도 모델에게 간다
  - [x] `refine_sql` 만 들여쓰기가 없는 것도 그대로
  - [x] JSON 파싱 + 랩과 같은 폴백. **`is_json_parsed` 로 실패를 따로 기록** —
        폴백은 "문제없다는 검토" 와 똑같이 생겼다
- [x] **프롬프트 축자 비교 테스트** ← 완료 기준 3 · `check_prompts()`
  - [x] 노트북에서 f-string 원문을 추출해 **렌더한 뒤** 대조. 3개 모두 일치
  - [x] 검사가 실제로 차이를 잡는지 확인 — 한 글자 · 앞 개행 · 뒤 공백 ·
        en-dash · 대소문자 · 들여쓰기 전부 검출

```bash
python -m sql_agent.sqlgen
```

### 배관 확인 — 실제 호출 1회

- [x] 랩의 질문으로 4단계를 손으로 이어봤다. **랩의 서술이 그대로 재현된다**

| 단계 | 결과 |
|---|---|
| `generate_sql` | `SUM(qty_delta * unit_price)` + `WHERE action='sale'` — 우리가 역산한 형태와 동일 |
| 실행 | **blue / −190,571** ← 랩 문서의 값 |
| `refine_sql` (텍스트만) | *"It fully answers the user's question"* → SQL 그대로 → ❌ |
| `refine_sql_external_feedback` | 부호 문제 지적 → `ABS(qty_delta)` → **white / 358,315** ✅ |

> 단발 관측이다. 수치는 5단계에서 N=10 으로 낸다.

## 4. 워크플로우와 판정기 [A]

- [x] **`sql_agent/scoring.py` — 정답 판정기** ([PLAN §6.2](PLAN.md))
  - [x] 오류 프레임 아님 · 1행 이상 · 첫 행 키 일치 · 값 ±0.01
  - [x] SQL 문자열은 보지 않는다. `ABS(qty_delta)` 와 `-qty_delta` 는 같은 답이다
  - [x] 실패해도 `value_delta` 를 남긴다 — 0.09 차이와 색이 다른 것은 다른 이야기다
  - [x] **LLM 없이 검증** — 정답 SQL 6/6 통과, 틀린 SQL 7종 전부 탈락,
        표현만 다른 SQL 4종(컬럼 순서 반대 포함) 전부 통과
- [x] `sql_agent/workflow.py` — `run_sql_workflow()` 대응
  - [x] 스키마 → V1 → 실행 → 검토 → V2 → 실행
  - [x] 랩은 반환값이 없다. **우리는 `WorkflowResult` 를 돌려준다**
        (기획서에는 "dict" 라고 적었으나 `final_result` 같은 파생값이 필요해 데이터클래스로)
  - [x] 조건 4개 — `none` / `text` / `feedback` / `feedback-t0` ([PLAN §5.4](PLAN.md))
  - [x] **첫 모델 호출 전에 `check_prompts()`** — 240회를 돌린 뒤 프롬프트가
        어긋나 있었음을 알면 전부 버려야 한다
- [x] `sql_agent/report.py` — 콘솔 + 파일 저장. **판정은 `scoring` 이 값을 보고 낸다**
- [x] `sql_agent/trace.py` — 단계별 소요·모델·온도·파싱 상태
- [x] `run.py` — CLI

```bash
python run.py --list                              # 평가 질문과 정답
python run.py --index 0 --condition feedback-t0   # 채점되는 실행
```

> ⚠ **옵션 이름이 기획서와 다르다.** `--reflection` → `--condition`,
> `--basename` → `--label`. 문서 본문이 이미 "조건"·"라벨" 로 부르고 있어 그쪽에 맞췄다.
> `--index` · `--list` 는 기획에 없던 것으로, **채점되는 실행과 아닌 실행을 가르는** 장치다.

### 4조건 실행 확인 (질문 0 · 관측 1회)

| 조건 | 결과 |
|---|---|
| `none` | FAIL — 첫 행에 정답 키 없음 (blue) |
| `text` | FAIL — 같음. 검토가 *"fully answers"* 라고 답했다 |
| `feedback` | PASS |
| **`feedback-t0`** | **PASS** — 온도를 `text` 와 같게 맞춰도 통과 |

## 5. 재현 검증 · 성공률 · 모델 비교 [A]

[PLAN §3](PLAN.md)의 완료 기준 7개와 대응한다.

### 5.1. 단일 실행 확인

- [ ] 질문 하나로 V1·V2 SQL 과 두 결과
- [ ] V1 결과가 음수인가 — 의미 오류가 실제로 발생하는지
- [ ] 검토 + V2 SQL 이 한 JSON 에서 파싱되는지
- [ ] 중간 산출물 전부 표시·저장
- [ ] 문법 오류 SQL 이 조용히 넘어가지 않는지

### 5.2. 조건별 성공률 — 완료 기준 4

- [ ] `--repeat N` (기본 10) · 조건 4개 각각
- [ ] 산출물 `runs/{시각}_{라벨}/{조건}/{회차}/`

```
none          x/10
text          y/10
feedback      z/10     ← 랩 기본 (temperature 1.0)
feedback-t0   w/10     ← 통제 조건 (temperature 0)
```

- [ ] **`z > y` 방향성**을 확인한다. 특정 실행의 성패는 판정 근거가 아니다
- [ ] **`w` vs `y` 가 핵심 비교다** — temperature 가 같으므로 실행 결과의 효과만 남는다
- [ ] `y`·`w` 는 `temperature=0` 이라 분산이 작을 것이다. 조건별로 나눠 해석한다

### 5.3. 모델 조합 실험 — 완료 기준 7

랩 Final Takeaways 4번 — *"Experiment with different LLM models to compare
performance and **accuracy**."* 랩 §3.4 가 네 모델을 나열한다.

- [ ] `gpt-4.1` (랩 기본) · `gpt-4o` · `gpt-4.1-mini` · `gpt-3.5-turbo`
- [ ] 생성 모델과 평가 모델을 따로 바꿔본다
- [ ] **육안이 아니라 성공률로 비교**한다 — 판정기가 있으므로 가능하다
- [ ] 랩의 *"gpt-4.1 often gives the best results for self-reflection"* 을 확인
- [ ] `README.md` 에 실제 숫자 채우기

## 6. 확장 [B] — A 완료 후

- [ ] **B1. 정답 데이터셋 정확도** ← 05번 레슨의 87%↔95%
  - [x] 질문 6개는 [PLAN §6.1](PLAN.md) 에 확정 — 전부 정답 존재를 확인함
  - [ ] 10~15개로 확장. **넣기 전에 반드시 돌려본다**
  - [ ] 질문 설계 제약 지킨다 — 시간 조건 불가, `restock` 금액 불가
  - [ ] 질문에 해석을 못박는다 (*"sale events only"*)
  - [ ] **집계는 두 벌** — 전체 평균 + 부호·순서 질문만
  - [ ] 오답을 **해석 차이 / 실제 오류**로 분류
  - [ ] 5단계의 판정기·집계 코드를 그대로 쓴다
- [ ] **B2. SQL 실행 오류 명시적 되먹임** — 랩이 이미 절반 한다 ([PLAN §5.6](PLAN.md))

## 7. 회고

- [ ] 조건 4개의 실제 성공률 — 특히 `w` vs `y`
- [ ] 모델별 정확도
- [ ] **공통 모듈 추출 판단** — 실제로 무엇이 같았는지 보고
- [ ] `notes/retrospectives/` 에 기록

---

## 규칙

1. **랩의 계약을 바꾸지 않는다.** 프롬프트 문구, 함수 경계, 파싱 폴백은 그대로.
   구조를 "더 낫게" 바꾸고 싶으면 B 로 미룬다
2. **프롬프트는 축자다.** 공백·들여쓰기까지. 조건 4는 프롬프트가 아니라 호출 인자만 바꾼다
3. **A 가 끝나기 전에 B 를 시작하지 않는다**
4. LLM 없이 검증 가능한 층(데이터·실행·판정기)을 먼저 굳힌다.
   **특히 랩과 같은 숫자가 나오는지부터**
5. **단발 LLM 결과를 판정 근거로 쓰지 않는다.** 랩도 *"LLMs are stochastic"* 이라고 명시한다
6. **평가 질문은 넣기 전에 실행해본다**
7. **공개 이름은 기획서를 먼저 확인하고 짓는다.** 함수명 · CLI 옵션 · 반환 타입처럼
   밖에서 부르는 이름은 기획서에 이미 적힌 것이 있다. 더 나은 이름이 떠올라도
   **바꾸는 순간 그 자리에서 문서도 고치고, 왜 바꿨는지 남긴다**

   > 3단계까지 세 번 어겼다 — `execute_sql`→`run_query`, `review_sql`→`refine_sql`,
   > `--reflection`→`--condition`. 매번 코드를 먼저 쓰고 문서를 나중에 맞췄다.
   > 문서가 조용히 코드를 따라가면 기획은 검증 기준이 아니라 사후 기록이 된다.

8. SQL 실행은 항상 읽기 전용 연결
9. 조용한 예외 삼킴 금지 — `execute_sql` 의 오류→DataFrame 은 되먹이는 것이므로
   플래그로 구분한다
10. 단계 완료 시 체크박스를 갱신한다
