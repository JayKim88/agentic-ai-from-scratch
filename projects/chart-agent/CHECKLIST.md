# 작업 체크리스트

> 기획서: [PLAN.md](PLAN.md) · 회고: [chart-agent-lab-findings.md](../../notes/retrospectives/chart-agent-lab-findings.md)
> 최종 수정 2026-08-04

**A(1~5단계)가 랩 재현, B(6단계)가 확장. A 없이 B를 하지 않는다.**

| 단계 | 구분 | 상태 |
|---|---|---|
| 0. 준비 | — | ✅ |
| 1. 데이터 계층 | A | ✅ |
| 2. 실행 계층 | A | ✅ |
| 3. LLM 계층 | A | ✅ |
| 4. 4단계 워크플로우 | A | ✅ |
| 5. 랩 재현 검증 | A | ✅ |
| 6. 확장 (B1~B4) | B | ⬜ |
| 7. 회고 | — | ⬜ |

---

## 0. 준비 ✅

- [x] `PLAN.md` · 이 문서 작성
- [x] `OPENAI_API_KEY` · `ANTHROPIC_API_KEY` 확인
- [x] `pandas` 3.0.5 / `matplotlib` 3.11.1 확인
- [x] 랩 자료를 [`labs/module-2/`](../../labs/module-2/)로 — HTML · CSV · 차트 2장
- [x] `.gitignore`에 `runs/*/v*_work/` 추가 — 실행 결과는 커밋한다
- [ ] ⏸ **`utils.py`는 3단계 완료 후에 연다** — `vision.py`의 정답지다

## 1. 데이터 계층 [A] ✅

- [x] `dataset.py` — 시드 고정 생성기 (폴백용)
- [x] `load_and_prepare_data(path)` — 랩 계약. 스키마 불일치 → `ValueError`
- [x] `validate_dataset(df)` — 랩 V1이 의존하는 불변식 강제
- [x] `resolve_dataset_path()` — 랩 CSV 우선, 없으면 생성본
- [x] pandas 3.0.5 검증 ← 첫 관문

### `validate_dataset`이 막는 것

랩 V1은 두 해를 `coffee_name`으로 **inner join** 한다. 한쪽 분기에 음료가 빠지면
**에러 없이 차트에서 사라진다.**

| 검사 | 실패 시 |
|---|---|
| 관측 가격 5개 재현 | 생성기 가격표 드리프트 |
| 두 Q1이 비어 있지 않음 | 비교 불가 |
| **두 Q1에 8종 전부** | inner join이 조용히 떨어뜨림 |
| Q1 2025 행 수 > Q1 2024 | 증가가 안 보임 |

가드 4개 전부 인위적 위반으로 발동 확인. 실물·생성본 둘 다 통과한다.

> "두 Q1이 3개월 온전" 검사는 제거했다 — 실물이 반증했다
> ([회고 §3](../../notes/retrospectives/chart-agent-lab-findings.md)).

### pandas 3.0.5 — 랩 V1 코드를 그대로 재생

```python
q1_2024 = df[(df['year'] == 2024) & (df['quarter'] == 1)]
sales_2024 = q1_2024.groupby('coffee_name')['price'].sum().reset_index()
comparison = pd.merge(sales_2024, sales_2025, on='coffee_name', suffixes=('_2024','_2025'))
```

→ **8행, 누락 없음.** `date` dtype이 `datetime64[us]`(2.x는 `[ns]`)이지만 동작 차이 없음.

**검증**
```bash
cd projects/chart-agent
../../venv/bin/python -m chart_agent.dataset     # 재생성 + 불변식 검사
```

## 2. 실행 계층 [A] ✅

- [x] `<execute_python>` 추출 — 랩과 동일한 정규식
- [x] **태그 없으면 `MissingCodeBlockError`** — 랩의 `if match:`는 else가 없다
- [x] subprocess + `-I`, 부모의 df를 **pickle로 전달**
- [x] 실행 전역은 `['df']` 뿐 — 랩의 `exec_globals`와 동일
- [x] 타임아웃 30초, 메시지에 실제 초 반영
- [x] stdout / stderr / 종료코드 반환

### 성공 판정은 종료 코드만으로 하지 않는다

`succeeded` = **종료 코드 0 AND 차트 파일 존재**

| 상황 | 종료 코드 | 차트 | 판정 |
|---|---|---|---|
| 랩 V1 원본 | 0 | ✅ | 성공 (1.1초, `backend=Agg`) |
| `KeyError` | 1 | ❌ | 실패 |
| `savefig` 누락 | **0** | ❌ | **실패** |
| 다른 경로에 저장 | **0** | ❌ | **실패** |
| 무한 루프 | -1 | ❌ | 타임아웃 |

아래 둘이 종료 코드만 보면 통과한다. 랩 프롬프트가 저장 경로를 명시하므로 지시 위반이다.
`failure_summary()`가 이를 한 문장으로 만들어 B1 되먹임에 넣을 수 있게 한다.

설계 근거는 [`executor.py` 독스트링](chart_agent/executor.py)에 있다.

**검증**
```bash
../../venv/bin/python -c "
from chart_agent.dataset import load_and_prepare_data, resolve_dataset_path
from chart_agent.executor import execute_code
df = load_and_prepare_data(resolve_dataset_path())
r = execute_code('print(len(df))', df, '/tmp/c.png', '/tmp/w')
print(r.returncode, r.stdout.strip())
"
```

## 3. LLM 계층 [A] ✅

- [x] `config.py` — 모델 기본값, 키 검증, `provider:model` 라우팅
- [x] `llm.py` — aisuite 텍스트/이미지 호출 (`get_response` + `image_*_call` 대응)
- [x] `vision.py` — **provider별 이미지 메시지 구성** ← 학습 핵심
- [x] `codegen.py` — 스키마 9컬럼 주입 프롬프트

### aisuite가 덮지 않는 것이 둘이었다

이미지 형식은 예상대로였고, **토큰 상한 인자 이름은 예상 밖**이었다.

| | OpenAI | Anthropic |
|---|---|---|
| 이미지 블록 | `image_url` + data URI | `source.type = "base64"` |
| 블록 순서 | 텍스트 → 이미지 | **이미지 → 텍스트** (Anthropic 권장) |
| 토큰 상한 | 선택. gpt-5는 `max_completion_tokens`, gpt-4.1은 `max_tokens` | **필수** `max_tokens` |

aisuite는 `content`를 양쪽 다 그대로 통과시키므로 **블록만 맞게 만들면 호출은 aisuite로 통일**된다.
추상화가 덮는 것은 *호출*이지 *메시지 형식*이 아니다.

토큰 상한은 **OpenAI에 아예 보내지 않는다.** 선택 인자인데 모델 계열마다 이름이 달라서,
보내지 않는 쪽이 계열을 판별하는 것보다 견고하다. Anthropic은 필수라 보낸다.

### 이미지가 실제로 전달되는지 — 완료 기준 3

이미지에만 있는 정보(제목·눈금·색상)를 물어 확인했다. 지시문이나 코드에는 없는 것들이다.

| 모델 | 제목 | 최대 눈금 | 색상 |
|---|---|---|---|
| `openai:gpt-5` | Q1 Coffee Sales Comparison: 2024 vs 2025 | 700 | Blue and orange |
| `openai:gpt-4.1` | 〃 | 700 | Blue and orange |
| `anthropic:claude-sonnet-5` | 〃 | 600 | Blue and Orange |

입력은 랩의 실제 [`chart_v1.png`](../../labs/module-2/chart_v1.png).
`log_request=True`로 요청 페이로드도 남는다 — 비평이 다르다는 것만으로는 증명이 안 되기 때문이다.

### V1 생성 → 실행 (랩 step 1~2)

`gpt-4.1-mini` 4.6초 → 22줄 코드 → 실행 1.1초 → 차트 생성 성공.
프롬프트 1,413자에 스키마 9행·요구사항 8개·`dpi=300` 전부 포함 확인.

**검증**
```bash
cd projects/chart-agent
../../venv/bin/python -c "
from chart_agent import codegen
from chart_agent.executor import extract_code
r = codegen.generate_chart_code('Compare Q1 coffee sales in 2024 and 2025', '/tmp/c.png')
print(extract_code(r)[:200])
"
```

## 4. 4단계 워크플로우 [A] ✅

- [x] `reflect.py` — `reflect_on_image_and_regenerate()` 대응
  - [x] 입력: 이미지 + 지시문 + 모델명 + V2 경로 + **V1 코드** (랩 인자 순서 그대로)
  - [x] 출력: 1행 JSON → 개행 → `<execute_python>` 블록
  - [x] **3단 폴백 파싱.** 실패 시 `parse_error`에 남기고 원문도 보존
  - [x] `refined_code` JSON 키는 만들지 않는다 — 랩의 죽은 키
  - [x] 스키마 블록은 **두 개**. 랩의 두 프롬프트가 문구를 달리 쓰고,
        프롬프트는 모델이 읽는 입력이라 축자로 둔다.
        `validate_schema_blocks()`가 **컬럼 이름 누락만** 검사한다 —
        나머지는 사람이 쓴 지시문이라 `dtypes`로 만들 수 없다
  - [x] 태그 없으면 `MissingCodeBlockError` (랩은 빈 문자열로 대체)
- [x] `workflow.py` — `run_workflow()` 대응
  - [x] 파라미터 5개, **반환 dict 5키**
  - [x] `image_basename` → `{base}_v1.png` / `{base}_v2.png`
  - [x] **실행마다 `runs/{시각}_{라벨}/` 폴더** — 같은 라벨로 여러 번 돌려도 덮어쓰지 않는다.
        랩은 사람에게 "매번 이름을 바꾸라"고 하지만 그 부담을 코드가 진다
  - [x] **실행 실패 시 `failure_summary()`를 담아 중단** (재시도는 B1)
  - [x] `generate_and_execute_v1` / `reflect_and_execute_v2` 분리 → 단계 단독 실행 가능
- [x] `report.py` — `print_html` 대응
  - [x] 데이터 샘플 5행 · 추출 코드 · V1 경로 · **비평 원문** · V2 코드 · V2 경로
  - [x] 산출물 7종 저장 — 단계마다 **보낸 것·받은 것·파싱한 것**
        (`v1_prompt` `v1_raw` `v1_code` `v2_prompt` `reflection_raw` `feedback` `v2_code`)
  - [x] **실행 직전에 저장.** 어디서 깨지든 그때까지의 기록이 디스크에 남는다 — 네 실패 경로로 검증
  - [x] `v*_work/` 는 성공 시 삭제, 실패 시 보존 (traceback 줄 번호 대조용)
- [x] `trace.py` — 단계별 소요·모델·산출물 경로 JSON
- [x] `run.py` — CLI + 단계 단독 실행

### 실행 결과 — 강의 지시문 그대로

```
Step 1  V1 코드 생성    gpt-4.1-mini            7.1s
Step 2  V1 실행         20260805-132356_baseline/…_v1.png   120,548 B
Step 3  비평 + 수정     gpt-5                   24.7s
Step 4  V2 실행         20260805-132356_baseline/…_v2.png   181,123 B
```

**V1의 결함:** x축은 연도인데 레이블이 `Coffee Name`, 범례 제목은 `Year` 인데 음료가 나열됐다.
축과 범례가 서로 뒤바뀐 상태.

**비평이 정확히 그것을 지적했다:**

> *"the x-axis shows years but is labeled 'Coffee Name', and the legend title 'Year'
> actually lists coffee types"*

**V2:** x축 = 음료명, 범례 = 2024/2025, 정렬·그리드 추가. **연도 비교가 유지된다** —
랩의 실물 V2 가 잃어버렸던 바로 그 차원이다.

### 단계 단독 실행

```bash
python run.py --only v1 --basename partial              # 랩 3.1~3.2
python run.py --from-chart <경로> --basename fromlab    # 랩 3.3~3.4
```

`--from-chart` 로 랩의 실물 `chart_v1.png` 을 비평시키니
*"coffee names are hard to read due to steep rotation"* 을 짚었다 — 회고에 기록한 레이블 잘림이다.

> V1 코드 없이 이미지만 넘어가므로 비평 입력이 약해진다. 그대로 두되 경고를 띄운다.

**검증**
```bash
cd projects/chart-agent
../../venv/bin/python run.py --basename demo -v
```

## 5. 랩 재현 검증 [A] ✅

[PLAN §2](PLAN.md)의 완료 기준 8개와 대응한다.

- [x] 강의 지시문으로 실행 → V1·V2 생성
- [x] 추출된 코드 육안 확인
- [x] **이미지가 실제로 전달되는지** — 요청 페이로드 요약이 트레이스에 남는다
- [x] 비평 + V2 코드가 한 응답에서 파싱되는지 — `reflection_raw.txt` 로 확인
- [x] 중간 산출물 전부 표시·저장 (프롬프트 2 · 원문 2 · 파싱 3)
- [x] **비평이 V1의 결함을 지적했는지**
- [x] **V2 > V1 육안 확인**
- [x] 단계 단독 실행 동작
- [x] `--basename` 반복 실행 → 실행 폴더가 분리돼 덮어쓰지 않음
- [x] **모델 조합 실험** — 랩이 권장한 활동
- [x] `README.md` 에 실제 출력 반영

### 커밋된 실행 두 개

```
runs/20260805-132356_baseline/       전체 워크플로우. gpt-4.1-mini → gpt-5
runs/20260805-134121_claude-fixed/   같은 V1 을 claude-sonnet-5 가 비평
```

두 번째는 첫 번째의 `baseline_v1.png` 와 그 `v1_code.py` 를 그대로 입력받는다.
**비평 프롬프트가 저장 경로 한 줄만 다르므로**, 결과 차이는 모델 차이다.

### 모델 조합 실험 결과

| | gpt-5 | claude-sonnet-5 |
|---|---|---|
| 초점 | **V1 코드의 구현 방식** — union-sorting, pivot 이 더 깔끔 | **그림의 지각 문제** — 낮은 값 막대 구분, 범례가 막대를 가림 |
| V2 선택 | 세로 막대 유지 + 정렬·그리드 | **가로 막대로 전환** + 값 레이블 |

같은 입력인데 **읽는 것이 다르다.** 랩이 "모델을 바꿔보라"고 한 이유가 여기 있다.

### ⚠ 실험 중 발견한 `--from-chart` 결함

처음 두 번은 Claude 가 실행 불가능한 코드를 냈다.

```python
df = pd.read_csv('…/coffee_sales.csv') if False else None
q1_2024 = df[(df['year'] == 2024) & …]     # TypeError: 'NoneType' …
```

원인은 모델이 아니라 **우리 쪽이었다.** `--from-chart` 가 V1 코드 자리에
`(not available)` 을 넣고 있었다.

랩의 3.3 셀은 노트북 변수로 `code_v1` 을 갖고 있다. 단계 단독 실행의 *형태*는
재현했지만 *상태*는 재현하지 못한 것이다. 그리고 이 단계의 출력은 **수정된 코드**라,
고칠 코드를 주지 않으면 모델이 처음부터 새로 쓴다 — 그러다 "파일을 읽지 마라" 제약과
충돌했다.

차트 옆의 `artifacts/v1_code.py` 를 읽도록 고쳤고, 없으면 실패한다.
경고만 띄우고 약한 입력으로 진행하지 않는다.

> 같은 모델·같은 입력으로 다시 돌리니 통과했다.
> **비평 품질과 실행 가능한 코드는 별개**라는 것도 함께 드러났다 —
> 완료 기준 5번과 6번을 따로 둔 이유다.

## 6. 확장 [B] — A 완료 후

- [ ] **B1. 실행 오류 되먹임** (우선순위 높음)
  - [ ] traceback을 재생성 프롬프트에 주입, 재시도 2회 상한
  - [ ] 발동 횟수를 트레이스에 기록
  - [ ] 랩 프롬프트의 `date` 경고 3회 반복을 **덜어낼 수 있는지** 실험
- [ ] **B2. 객관 채점** — `plt.savefig` 래핑 → Figure 메타 덤프
  - [ ] 실행 성공 / 제목 / x·y축 / 범례 / dpi=300 ← 랩 요구사항 그대로
  - [ ] **지시문 충족** ← 가장 중요. 실물 V2가 이것만 놓치고 만점을 받는다
  - [ ] 계열 구분 (누적·겹침) — 퇴행 검출용
- [ ] **B3. 루브릭 채점** (우선순위 낮음)
  - [ ] 이진 기준만, 단일 이미지, 채점 모델 분리
  - [ ] 기준: 차트 유형 적절성 / 색상 구분
- [ ] **B4. 비평/수정 분리 실험** — 플래그로만. 기본은 랩대로 합친 형태

## 7. 회고

- [ ] **`utils.py` 대조** — 3단계 `vision.py`와 비교
- [ ] B1이 값을 했는지 판정
- [ ] 모듈 1과의 코드 중복 검토
- [ ] [회고 문서](../../notes/retrospectives/chart-agent-lab-findings.md) 갱신

---

## 규칙

1. **랩의 계약을 바꾸지 않는다.** 함수 경계, 반환 5키, 출력 형식, 파싱 폴백은 그대로.
   구조를 "더 낫게" 바꾸고 싶으면 B로 미룬다
2. **A가 끝나기 전에 B를 시작하지 않는다**
3. LLM 없이 검증 가능한 층(데이터·실행)을 먼저 굳힌다.
   흔들리면 모델 문제인지 코드 문제인지 구분할 수 없다
4. `exec` 대상은 항상 subprocess
5. 조용한 예외 삼킴 금지 — 랩의 `if match:` 패턴을 따라하지 않는다
6. 단계 완료 시 체크박스를 갱신한다
