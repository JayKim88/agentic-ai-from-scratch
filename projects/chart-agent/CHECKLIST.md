# 작업 체크리스트

> 기획서: [PLAN.md](PLAN.md) · 최종 수정 2026-08-04

**A(1~5단계)가 랩 재현이고, B(6단계)가 확장이다. A 없이 B를 하지 않는다.**

## 진행 상황

| 단계 | 구분 | 상태 |
|---|---|---|
| 0. 준비 | — | ✅ 완료 |
| 1. 데이터 계층 | A | ✅ 완료 (5,509행, 검증 통과) |
| 2. 실행 계층 | A | ✅ 완료 (1.1s/실행) |
| 3. LLM 계층 (텍스트 + 이미지) | A | ⬜ |
| 4. 4단계 워크플로우 | A | ⬜ |
| 5. 랩 재현 검증 | A | ⬜ |
| 6. 확장 (B1~B4) | B | ⬜ |
| 7. 회고 | — | ⬜ |

---

## 0. 준비

- [x] 기획서 작성 (`PLAN.md`)
- [x] 작업 체크리스트 작성 (이 문서)
- [x] `OPENAI_API_KEY` 확인 — 설정됨
- [x] `ANTHROPIC_API_KEY` 확인 — 설정됨 (검토 모델용)
- [x] `pandas` 3.0.5 / `matplotlib` 3.11.1 설치 확인
- [x] 랩 HTML을 [`labs/module-2/`](../../labs/module-2/M2_UGL_1.html)로 이동
- [x] `.gitignore`에 `projects/chart-agent/{charts,traces}/` 추가

## 1. 데이터 계층 [A] — ✅ 완료

- [x] `dataset.py` — 시드 고정 생성기 (`RANDOM_SEED = 20260804`)
  - [x] 스키마 6컬럼 + 파생 3컬럼 (`dt.quarter`/`dt.month`/`dt.year`)
  - [x] `date`는 `datetime64[us]`, `time`은 문자열 HH:MM (분리 유지)
  - [x] **음료 8종** (슬라이드 V2 범례에서 확정)
  - [x] ⚠ **`quantity` 컬럼 없음.** 1행 = 거래 1건. 근거는 랩의 `df.sample(n=5)`
        출력 표 (헤더 9개, 각 행 9셀, 생략 표시 없음) — [PLAN §5](PLAN.md)
  - [x] 판매량 차이는 **행 수로** — Q1 2024 784행 → Q1 2025 1,339행
  - [x] **기간 2024-01-01 ~ 2025-03-31** — Q1 양쪽 3개월 온전
  - [x] `time`·`cash_type`·`card`도 포함 (스키마 주입 대상). 현금 행의 `card`는 빈 문자열
- [x] `load_and_prepare_data(path)` — 랩 `utils` 함수와 동일한 계약
  - [x] 스키마 불일치 → `ValueError`. 파일 부재 → `FileNotFoundError` + 생성 명령 안내
- [x] `validate_dataset(df)` — **랩 V1 코드가 의존하는 불변식을 코드로 강제**
- [x] **pandas 3.0.5 동작 검증** ← 첫 관문 통과
- [x] `data/coffee_sales.csv` 생성 (5,509행 / 311KB) 후 커밋

### `validate_dataset` — 조용히 깨질 수 있는 것들을 막는다

랩 V1 코드는 두 해를 `coffee_name`으로 **inner join** 한다. 한쪽 분기에 음료가 하나
빠지면 **에러 없이 차트에서 사라진다.** 시드나 가중치를 건드렸을 때 이게 조용히
깨지면 안 되므로 불변식을 함수로 박아뒀다.

| 검사 | 실패 시 |
|---|---|
| 관측 가격 5개 재현 | 가격표·`PRICE_RISE_DATE` 드리프트 검출 |
| 두 Q1이 비어 있지 않음 | 비교 자체가 불가능 |
| 두 Q1이 3개월 온전 | 기간 불균형 비교 |
| **두 Q1에 8종 전부** | inner join이 조용히 떨어뜨림 |
| Q1 2025 행 수 > Q1 2024 | 비교에 증가가 안 보임 |

가드 5개 전부 인위적 위반으로 발동 확인했다.

> **관측 가격은 "그 날 그 음료가 팔렸는가"가 아니라 "그 날 그 음료의 가격"으로 검증한다.**
> 특정 행의 존재는 난수 추첨이라 재현 대상이 아니다. 처음엔 행 존재를 검사해서
> 지터 모델을 바꾸자마자 오탐이 났다.

### 관측값 재현 — 랩 `df.sample(n=5)` 표

| 음료 | 날짜 | 가격 |
|---|---|---|
| Latte | 2024-07-19 | 3.282 |
| Espresso | 2024-08-07 | 1.812 |
| Latte | 2024-12-04 | **3.576** |
| Cortado | 2024-12-05 | 2.596 |
| Americano | 2025-02-10 | 2.596 |

Latte가 7월 3.282 → 12월 3.576이므로 **그 사이 가격 인상**이 있었다.
`PRICE_RISE_DATE = 2024-10-01`로 모델링해 5개가 전부 맞아떨어진다.

### pandas 3.0.5 호환 — 랩 V1 코드를 그대로 재생

```python
q1_2024 = df[(df['year'] == 2024) & (df['quarter'] == 1)]
sales_2024 = q1_2024.groupby('coffee_name')['price'].sum().reset_index()
comparison = pd.merge(sales_2024, sales_2025, on='coffee_name', suffixes=('_2024','_2025'))
```

→ **8행 반환, 누락 없음.** `.dt` 접근자·`groupby().sum().reset_index()`·`pd.merge()`
전부 정상. [CLAUDE.md](../../CLAUDE.md)가 경고한 pandas 2.x 가정 문제는 나타나지 않았다.

> pandas 3에서 `date` dtype이 `datetime64[us]`다 (2.x는 `[ns]`).
> 랩 프롬프트는 "datetime64"라고만 하므로 어긋나지 않는다.

**검증 명령**
```bash
cd projects/chart-agent
../../venv/bin/python -m chart_agent.dataset     # 재생성 + 불변식 검사
```

## 2. 실행 계층 [A] — ✅ 완료

- [x] `executor.py`
  - [x] `<execute_python>` 태그 추출 — 랩과 동일한 정규식
  - [x] **태그가 없으면 `MissingCodeBlockError`** — 랩의 `if match:`는 else가 없어 조용히 통과한다
  - [x] subprocess 실행, **부모의 df를 pickle로 전달**
  - [x] 실행 컨텍스트에 `df` 외에는 아무것도 없음 — 전역 확인 결과 `['df']`
  - [x] 타임아웃 30초(기본), 초과 시 종료. 메시지에 실제 초를 반영
  - [x] stdout / stderr / 종료코드 반환
- [x] 일부러 깨지는 코드로 오류 캡처 검증

### 자식은 프로젝트 코드를 쓰지 않는다

처음 구현은 자식이 `sys.path`에 프로젝트 루트를 넣고 `load_and_prepare_data`로
CSV를 **다시 로드**했다. 리뷰에서 세 가지 문제가 드러났다.

| 문제 | 내용 |
|---|---|
| 격리해놓고 구멍을 뚫음 | 작업 폴더의 `json.py`가 **stdlib을 가림**(실제 확인) |
| 경로 손계산 | `Path(__file__).parents[1]` — 패키지를 옮기면 조용히 깨짐 |
| **df 가정** | 자식이 항상 전체 CSV를 읽어, 걸러낸 df를 넘길 방법이 없음 |

**부모의 df를 pickle로 넘기니 셋이 한 번에 사라졌다.** 자식 코드가 이렇게 줄었다.

```python
import pandas as pd
df = pd.read_pickle(DF_PATH)
exec(compile(source, "<generated>", "exec"), {"df": df})
```

CSV가 아니라 pickle인 이유는 **dtype 보존**이다. CSV 왕복은 `date`를 문자열로
되돌리고 자식이 파생 컬럼을 다시 만들게 해서, 9컬럼 계약이 두 군데로 갈라진다.
비용은 쓰기 2ms / 읽기 1ms / 278KB.

`-I`(isolated mode)도 함께 쓴다. 작업 폴더를 모듈 검색 경로에서 빼므로
실행이 남긴 파일이 표준 라이브러리를 가리지 못한다. venv 패키지는 그대로 살아있다.

> pickle은 신뢰할 수 없는 파일에 쓰지 말라는 형식이지만 여기서는 해당 없다.
> 파일을 만드는 쪽이 우리 부모 프로세스이고, 자식은 어차피 LLM이 쓴 임의 코드를
> 실행 중이다. 새로 생기는 노출이 없다.

### 성공 판정은 종료 코드만으로 하지 않는다

`succeeded`는 **종료 코드 0 AND 차트 파일 존재**다.

| 상황 | 종료 코드 | 차트 | 판정 |
|---|---|---|---|
| 랩 V1 원본 | 0 | ✅ | 성공 — 1.14초, `backend=Agg` |
| `KeyError` | 1 | ❌ | 실패 — stderr에 원인 |
| `savefig` 누락 | **0** | ❌ | **실패** |
| 다른 경로에 저장 | **0** | ❌ | **실패** |
| 무한 루프 | -1 | ❌ | 실패 — 타임아웃 |

아래 둘이 종료 코드만 보면 통과해버리는 경우다. 랩 프롬프트가 저장 경로를
명시(`Save the figure as '{out_path_v1}'`)하는 이상 다른 데 저장한 것은 지시 위반이다.

`failure_summary()`가 이 판정을 한 문장으로 만들어 B1 되먹임에 그대로 넣을 수 있게 한다.

### 확인된 동작

```
가공된 df 전달   부모에서 Latte 필터 → 자식이 rows 1233, ['Latte'] 수신
dtype 보존       date=datetime64[us], year=int32
stdlib 가림 방지  작업 폴더에 json.py 를 둬도 stdlib json 이 임포트됨
실행 전역        ['df'] — pd 참조 시 NameError
```

**검증 명령**
```bash
cd projects/chart-agent
../../venv/bin/python -c "
from chart_agent.dataset import load_and_prepare_data
from chart_agent.executor import execute_code
df = load_and_prepare_data('data/coffee_sales.csv')
r = execute_code(\"print(len(df))\", df, '/tmp/c.png', '/tmp/w')
print(r.returncode, r.stdout.strip())
"
```

## 3. LLM 계층 [A]

- [ ] `config.py` — 모델명, 상수, 키 검증
- [ ] `llm.py` — aisuite 텍스트 호출 (`get_response` 대응)
- [ ] `vision.py` — **provider별 이미지 메시지 구성** ← 학습 핵심 1
  - [ ] `encode_image_b64(path)` → `(media_type, b64)`
  - [ ] OpenAI 형식 블록 (`image_url` + data URI)
  - [ ] Anthropic 형식 블록 (`source.type = "base64"`)
  - [ ] 모델명 prefix로 라우팅 — 랩은 `"claude" in lower or "anthropic" in lower`로 분기
  - [ ] **양쪽 실호출 검증** — 같은 이미지로 두 provider 모두 응답 확인.
        기본 경로는 OpenAI지만 Anthropic 경로도 반드시 한 번 태운다
- [ ] `codegen.py` — `generate_chart_code()` 대응
  - [ ] 역할 지정 + 출력 형식 강제 (태그 안에만, 설명 금지)
  - [ ] **스키마 9컬럼 프롬프트 주입** ← 랩의 핵심 기법. 모델은 CSV를 볼 수 없다
  - [ ] 요구사항 8개 (matplotlib / 제목·레이블·범례 / dpi=300 / `plt.show()` 금지 / `plt.close()` / import / `date` 타입)
  - [ ] 스키마 블록을 **공용 상수로 추출** — 랩은 두 프롬프트에 복붙해뒀다

## 4. 4단계 워크플로우 [A]

- [ ] `reflect.py` — `reflect_on_image_and_regenerate()` 대응
  - [ ] 입력: 이미지 + 지시문 + 모델명 + V2 경로 + **V1 코드**
  - [ ] 출력 형식: 1행 JSON `{"feedback": ...}` → 개행 → `<execute_python>` 블록
  - [ ] **3단 폴백 파싱** — 첫 줄 `json.loads` → 본문 첫 `{...}` → 실패 메시지를 feedback에 담기
  - [ ] 최종 실패도 기록은 남긴다 (조용한 무시 금지)
  - [ ] ⚠ **`refined_code` JSON 키를 만들지 말 것** — 랩 폴백 dict에 남아 있지만
        아무도 읽지 않는 죽은 키다. 코드는 태그에서만 뽑는다
- [ ] `workflow.py` — `run_workflow()` 대응
  - [ ] 파라미터: `dataset_path`, `user_instructions`, `generation_model`, `reflection_model`, `image_basename`
  - [ ] **반환 dict 5키**: `code_v1`, `chart_v1`, `feedback`, `code_v2`, `chart_v2`
  - [ ] `image_basename`으로 `{base}_v1.png` / `{base}_v2.png` 저장 ← 랩이 명시적으로 강조한 부분
  - [ ] **실행 실패 시 `failure_summary()`를 담아 중단.** 재시도는 하지 않는다 — B1 소관
- [ ] `report.py` — **`print_html` 대응** ← 빠뜨리기 쉬운 부분
  - [ ] **데이터 샘플 5행** ← `run_workflow` 첫 줄이 `df.sample(n=5)`를 보여준다
  - [ ] 단계마다 콘솔에 산출물 표시: 추출된 코드 → V1 경로 → **비평 원문** → V2 코드 → V2 경로
  - [ ] 산출물 전량을 파일로 저장 (코드 `.py`, 비평 `.txt`)
  - [ ] 랩 마크다운 원문: *"you'll see both the reflection written by the LLM and the new code it generated"*
- [ ] `trace.py` — 단계별 입출력 + 이미지 경로
- [ ] `run.py` — CLI
  - [ ] **단계 단독 실행** — 랩의 3.1~3.4 개별 실습 흐름 대응

```
# 전체 (랩 4장)
python run.py "Create a plot comparing Q1 coffee sales in 2024 and 2025" \
  --gen-model openai:gpt-4.1-mini \
  --reflect-model openai:gpt-5 \
  --basename drink_sales -v

# 단계 단독 (랩 3.1~3.4)
python run.py "..." --only v1                        # V1 생성·실행까지
python run.py "..." --from-chart charts/x_v1.png     # 비평부터

# provider 라우팅 검증
python run.py "..." --reflect-model anthropic:claude-sonnet-5
```

### A 단계에서 실행이 실패하면 멈춘다

V1이 실패하면 차트가 없고, 차트가 없으면 비평 단계가 성립하지 않는다
(멀티모달 입력이 이미지다). 랩도 `exec`에서 그대로 죽는다.

여기서 재시도를 넣으면 B1을 A로 끌어오는 것이고 **규칙 2번을 어긴다.**
대신 에러 메시지에 `failure_summary()`를 실어 무엇이 잘못됐는지 즉시 보이게 한다
— B1 없이도 진단은 된다.

## 5. 랩 재현 검증 [A] — 여기까지가 랩

[PLAN §2](PLAN.md)의 완료 기준 8개와 1:1 대응한다.

- [ ] 강의 지시문으로 실행 → V1·V2 두 장 생성
- [ ] 추출된 코드 육안 확인 — 태그 추출이 정상인지
- [ ] **이미지가 실제로 모델에 전달되는지 확인**
  - [ ] 요청 페이로드에 이미지 블록이 들어갔는지 로깅으로 확인
  - [ ] 비평이 **이미지에만 있는 정보**(축 눈금값·색상·막대 높이)를 언급하는지
        ← LLM은 비결정적이라 "이미지 없이 돌린 결과와 다르다"만으로는 증명이 안 된다
- [ ] 비평 텍스트 + V2 코드가 한 응답에서 파싱되는지
- [ ] 중간 산출물이 전부 표시·저장되는지 (추출 코드 / V1 / 비평 / V2 코드 / V2)
- [ ] **비평이 V1의 결함을 지적했는지** ← 완료 기준 5번
  - [ ] V1이 실제로 결함 있는 차트인지 — 슬라이드는 **누적 막대**, 노트북 출력은 **겹친 막대**.
        어느 쪽이든 "음료별 비교 불가"가 공통 결함
  - [ ] 비평이 헛소리인데 V2만 우연히 나아진 경우가 아닌지
- [ ] **V2 > V1 육안 확인** ← 랩의 학습 성과 그 자체
  - [ ] V2가 **분리된 그룹 막대**로 수렴하는지
- [ ] 단계 단독 실행(`--only v1`, `--from-chart`) 동작 확인
- [ ] `--basename` 바꿔 연속 실행 → 덮어쓰기 없음
- [ ] **모델 조합 실험** — 랩이 권장한 활동. 생성/검토 모델을 바꿔 결과 차이 관찰
- [ ] `README.md`에 실제 출력 채워넣기

## 6. 확장 [B] — A 완료 후

- [ ] **B1. 실행 오류 되먹임** (우선순위 높음)
  - [ ] 실행 실패 시 traceback을 재생성 프롬프트에 주입
  - [ ] 재시도 2회 상한, 초과 시 실패로 기록
  - [ ] 발동 횟수를 트레이스에 기록
  - [ ] 랩 프롬프트의 `date` 경고 3회 반복을 **덜어낼 수 있는지** 실험
- [ ] **B2. 객관 채점** (Figure 내성 검사)
  - [ ] `plt.savefig` 래핑 → 저장 직전 Figure 메타 JSON 덤프
  - [ ] 실행 성공 / 제목 / x·y축 레이블 / 범례 / dpi=300 ← **랩 프롬프트 요구사항 그대로**
  - [ ] 데이터 계열 수 ≥ 2
  - [ ] **계열이 시각적으로 구분되는가** — 누적(`bottom`)과 오프셋 없는 겹침을 함께 검출.
        특정 결함을 하드코딩하지 않는다 (V1 결함은 실행마다 다르다)
  - [ ] ~~눈금 레이블 겹침~~ 제외 — 렌더러 없이 텍스트 폭을 알 수 없다
- [ ] **B3. 루브릭 채점** (우선순위 낮음)
  - [ ] 이진 기준만, 1~5점 척도 금지
  - [ ] 단일 이미지 채점, 쌍대비교 금지
  - [ ] 채점 모델을 생성·검토와 분리
- [ ] **B4. 비평/수정 분리 실험** (우선순위 낮음)
  - [ ] 플래그로 제공. **기본값은 랩대로 합친 형태**
  - [ ] 두 방식의 V2 품질 비교
- [ ] `--partial-q1` 실험 — Q1 기간이 불균형할 때 비평이 지적하는지 ([PLAN §5 UNCERTAIN](PLAN.md))

## 7. 회고

- [ ] 랩 구현과 자체 구현의 차이 정리
- [ ] B1이 값을 했는지 판정 (몇 건 구제했나)
- [ ] 모듈 1과의 코드 중복 검토 — 공통 모듈 추출 여부 ([PLAN §9](PLAN.md))
- [ ] `notes/retrospectives/`에 기록

---

## 규칙

1. **랩의 계약을 바꾸지 않는다.** 함수 경계, 반환 dict의 5키, 출력 형식, 파싱 폴백은
   랩 그대로 간다. 구조를 "더 낫게" 바꾸고 싶으면 B로 미룬다.
2. **A가 끝나기 전에 B를 시작하지 않는다.** 확장이 본체를 밀어내면 랩을 구현한 게 아니다.
3. 1번(데이터)·2번(실행)이 3번(LLM)보다 먼저다. **LLM 없이 검증 가능한 층을 먼저 굳힌다.**
   여기가 흔들리면 모델 문제인지 코드 문제인지 구분할 수 없다.
4. `exec` 대상은 항상 subprocess. 인라인 `exec`로 되돌리지 않는다.
5. 조용한 예외 삼킴 금지. 랩의 `if match:` (else 없음) 패턴을 따라하지 않는다.
6. 각 단계 완료 시 이 문서의 체크박스를 갱신한다.
