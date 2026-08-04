# 작업 체크리스트

> 기획서: [PLAN.md](PLAN.md) · 최종 수정 2026-08-04

**A(1~5단계)가 랩 재현이고, B(6단계)가 확장이다. A 없이 B를 하지 않는다.**

## 진행 상황

| 단계 | 구분 | 상태 |
|---|---|---|
| 0. 준비 | — | ⬜ |
| 1. 데이터 계층 | A | ⬜ |
| 2. 실행 계층 | A | ⬜ |
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
- [ ] 랩 HTML을 `labs/module-2/`로 이동 (루트에 두지 않는다)
- [ ] `.gitignore`에 `projects/chart-agent/{charts,traces}/` 추가

## 1. 데이터 계층 [A]

- [ ] `dataset.py` — 시드 고정 생성기
  - [ ] 스키마 6컬럼: `date, time, cash_type, card, price, coffee_name`
  - [ ] 파생 3컬럼: `quarter, month, year` (정수) — **랩이 "already computed"라고 프롬프트에 명시**
  - [ ] `date`는 `datetime64`, `time`은 문자열 HH:MM (분리 유지)
  - [ ] 음료별 고정 가격 + 소폭 변동 (Espresso 1.812 / Cortado 2.596 / Latte 3.282~3.576)
  - [ ] **음료 8종** (슬라이드 V2 범례에서 확정): Americano · Americano with Milk ·
        Cappuccino · Cocoa · Cortado · Espresso · Hot Chocolate · Latte
  - [ ] **두 해 모두에 8종이 다 있을 것** — 랩 V1 코드가 `inner join`을 쓴다
  - [ ] ⚠ **`quantity` 컬럼을 만들지 말 것.** 랩 스키마에 없다.
        **1행 = 거래 1건**이고 판매량은 `price` 합계 또는 행 수로 센다.
        (랩 산문의 `coffee_type`/`quantity`/`revenue` 언급은 프롬프트와 어긋난 오기)
  - [ ] 판매량 차이는 **행 수로** 만든다 — 2025 Q1이 2024 Q1보다 많도록
  - [ ] **기간 2024-01-01 ~ 2025-03-31** — Q1 양쪽이 온전해야 랩의 비교가 성립
  - [ ] `time`·`cash_type`·`card`도 포함 — 이 지시문엔 안 쓰이지만
        랩이 9컬럼 전부를 프롬프트에 주입하고, 골라내는 것이 과제의 일부다
- [ ] `load_and_prepare_data(path)` — 랩 `utils` 함수와 동일한 계약
- [ ] **pandas 3.0.5 동작 검증** — `.dt.year`, `groupby().sum().reset_index()`, `pd.merge()` ← 첫 관문
- [ ] `data/coffee_sales.csv` 생성 후 커밋 (재현성)

**검증 명령**
```bash
./venv/bin/python -c "
from chart_agent.dataset import load_and_prepare_data
df = load_and_prepare_data('data/coffee_sales.csv')
print(df.dtypes)
print(df.groupby(['year','quarter']).size())
"
```

## 2. 실행 계층 [A]

- [ ] `executor.py`
  - [ ] `<execute_python>` 태그 추출 — 랩과 동일한 정규식 `r"<execute_python>([\s\S]*?)</execute_python>"`
  - [ ] **태그가 없을 때 명시적 실패** — 랩의 `if match:`는 else가 없어 조용히 통과한다
  - [ ] subprocess 실행, `df` 주입 — 프로세스 경계를 넘길 수 없으므로 **자식이 CSV를 재로드**
  - [ ] 실행 컨텍스트에 `df` 외에는 아무것도 넣지 않는다 —
        랩의 `exec_globals = {"df": df}`와 동일. 생성 코드가 import를 스스로 해야 한다
  - [ ] 타임아웃 30초, 초과 시 kill
  - [ ] stdout / stderr / 종료코드 반환
- [ ] 일부러 깨지는 코드로 오류 캡처 검증

> 랩은 인라인 `exec(code, {"df": df})`를 쓴다. subprocess로 바꾸는 이유는 두 가지다 —
> 예외가 전체 실행을 죽이지 않게 하고, **stderr를 확보**해 B1의 재료로 삼는다.
> 동작 결과(차트 생성)는 동일하다.

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

## 5. 랩 재현 검증 [A] — 여기까지가 랩

[PLAN §2](PLAN.md)의 완료 기준 6개와 1:1 대응한다.

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
