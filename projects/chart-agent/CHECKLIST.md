# 작업 체크리스트

> 기획서: [PLAN.md](PLAN.md) · 회고: [chart-agent-lab-findings.md](../../notes/retrospectives/chart-agent-lab-findings.md)
> 최종 수정 2026-08-04

**A(1~5단계)가 랩 재현, B(6단계)가 확장. A 없이 B를 하지 않는다.**

| 단계 | 구분 | 상태 |
|---|---|---|
| 0. 준비 | — | ✅ |
| 1. 데이터 계층 | A | ✅ |
| 2. 실행 계층 | A | ✅ |
| 3. LLM 계층 | A | ⬜ |
| 4. 4단계 워크플로우 | A | ⬜ |
| 5. 랩 재현 검증 | A | ⬜ |
| 6. 확장 (B1~B4) | B | ⬜ |
| 7. 회고 | — | ⬜ |

---

## 0. 준비 ✅

- [x] `PLAN.md` · 이 문서 작성
- [x] `OPENAI_API_KEY` · `ANTHROPIC_API_KEY` 확인
- [x] `pandas` 3.0.5 / `matplotlib` 3.11.1 확인
- [x] 랩 자료를 [`labs/module-2/`](../../labs/module-2/)로 — HTML · CSV · 차트 2장
- [x] `.gitignore`에 `charts/` `traces/` 추가
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

## 3. LLM 계층 [A]

- [ ] `config.py` — 모델명, 상수, 키 검증
- [ ] `llm.py` — aisuite 텍스트 호출 (`get_response` 대응)
- [ ] `vision.py` — **provider별 이미지 메시지 구성** ← 학습 핵심
  - [ ] `encode_image_b64(path)` → `(media_type, b64)`
  - [ ] OpenAI 블록 (`image_url` + data URI)
  - [ ] Anthropic 블록 (`source.type = "base64"`)
  - [ ] 모델명 prefix 라우팅 — 랩은 `"claude" in lower or "anthropic" in lower`
  - [ ] **양쪽 실호출 검증** — 기본은 OpenAI지만 Anthropic도 한 번 태운다
- [ ] `codegen.py` — `generate_chart_code()` 대응
  - [ ] 역할 지정 + 출력 형식 강제
  - [ ] **스키마 9컬럼 주입** ← 랩의 핵심 기법
  - [ ] 요구사항 8개
  - [ ] 스키마 블록을 **공용 상수로** — 랩은 두 프롬프트에 복붙해뒀다

## 4. 4단계 워크플로우 [A]

- [ ] `reflect.py` — `reflect_on_image_and_regenerate()` 대응
  - [ ] 입력: 이미지 + 지시문 + 모델명 + V2 경로 + **V1 코드**
  - [ ] 출력: 1행 JSON → 개행 → `<execute_python>` 블록
  - [ ] **3단 폴백 파싱.** 최종 실패도 기록은 남긴다
  - [ ] `refined_code` JSON 키는 만들지 않는다 — 랩의 죽은 키
- [ ] `workflow.py` — `run_workflow()` 대응
  - [ ] 파라미터 5개, **반환 dict 5키**
  - [ ] `image_basename` → `{base}_v1.png` / `{base}_v2.png`
  - [ ] **실행 실패 시 `failure_summary()`를 담아 중단** (재시도는 B1)
- [ ] `report.py` — `print_html` 대응 ← 빠뜨리기 쉬움
  - [ ] 데이터 샘플 5행 ← `run_workflow` 첫 줄
  - [ ] 추출 코드 → V1 경로 → **비평 원문** → V2 코드 → V2 경로
  - [ ] 산출물 전량 파일 저장
- [ ] `trace.py` — 단계별 입출력 + 이미지 경로
- [ ] `run.py` — CLI + **단계 단독 실행**

```bash
python run.py "Create a plot comparing Q1 coffee sales in 2024 and 2025" \
  --gen-model openai:gpt-4.1-mini --reflect-model openai:gpt-5 --basename drink_sales -v

python run.py "..." --only v1                     # 랩 3.1~3.2
python run.py "..." --from-chart charts/x_v1.png  # 랩 3.3~3.4
python run.py "..." --reflect-model anthropic:claude-sonnet-5   # provider 라우팅
```

> **A 단계에서 실행이 실패하면 멈춘다.** 차트가 없으면 비평이 성립하지 않는다.
> 재시도를 넣으면 B1을 A로 끌어오는 것이라 규칙 2번을 어긴다.

## 5. 랩 재현 검증 [A] — 여기까지가 랩

[PLAN §2](PLAN.md)의 완료 기준 8개와 대응한다.

- [ ] 강의 지시문으로 실행 → V1·V2 생성
- [ ] 추출된 코드 육안 확인
- [ ] **이미지가 실제로 전달되는지**
  - [ ] 요청 페이로드 로깅
  - [ ] 비평이 **이미지에만 있는 정보**(축 눈금값·색상·막대 높이)를 언급하는지
        ← LLM은 비결정적이라 "이미지 없이 돌린 결과와 다르다"로는 증명이 안 된다
- [ ] 비평 + V2 코드가 한 응답에서 파싱되는지
- [ ] 중간 산출물 전부 표시·저장
- [ ] **비평이 V1의 결함을 지적했는지** ← 완료 기준 5
  - [ ] 비평이 헛소리인데 V2만 우연히 나아진 경우가 아닌지
- [ ] **V2 > V1 육안 확인** ← 완료 기준 6
- [ ] 단계 단독 실행 동작
- [ ] `--basename` 바꿔 연속 실행 → 덮어쓰기 없음
- [ ] **모델 조합 실험** — 랩이 권장한 활동
- [ ] `README.md`에 실제 출력 채우기

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
