# 차트 에이전트 — 기획서

> DeepLearning.AI *Agentic AI* 모듈 2 ungraded 랩 "Chart Generation"을 자체 구현하는 프로젝트.
> 작성일 2026-08-04

## 1. 배경

모듈 1과 달리 **랩 노트북의 HTML 내보내기를 확보했다** —
[`labs/module-2/M2_UGL_1.html`](../../labs/module-2/M2_UGL_1.html) (340KB).
코드 셀 25개·마크다운 셀 20개가 모두 들어 있어 함수 4개와 프롬프트 전문을 확인했다.

즉 이 프로젝트는 백지에서 추측하는 작업이 아니라 **명세가 있는 구현**이다.
따라서 기준은 하나다 — **랩이 만들고자 한 것을 만든다.**

### 확보하지 못한 것

| 항목 | 대응 |
|---|---|
| `utils.py` | 직접 구현. 호출부에 함수 7개의 시그니처·반환형이 전부 노출됨 |
| `coffee_sales.csv` | 생성. 출력 표본에 스키마와 값 범위가 드러남 |

```
load_and_prepare_data(path)          → DataFrame
print_html(content, title, is_image)  → 노트북 표시
get_response(model, prompt)           → str
encode_image_b64(path)                → (media_type, b64)
image_openai_call(model, prompt, media_type, b64)    → str
image_anthropic_call(model, prompt, media_type, b64) → str
ensure_execute_python_tags(body)      → str
```

## 2. 목표

랩이 명시한 학습 성과를 그대로 가져온다.

> *"By the end of this lab, you will have implemented the reflection pattern in code
> and used it to improve a data visualization."*

**멀티모달 LLM이 생성된 차트를 보고 비평한 뒤 코드를 고쳐 더 나은 차트를 만든다.**
이것이 본체이고, 나머지는 전부 부차적이다.

### 랩이 정의한 4단계

| # | 단계 | 랩 원문 |
|---|---|---|
| 1 | Generate an initial version (V1) | LLM으로 첫 플로팅 코드 생성 |
| 2 | Execute code and create chart | 생성된 코드를 실행해 차트 표시 |
| 3 | Reflect on the output | **코드와 차트를 함께** LLM으로 평가 |
| 4 | Generate and execute improved version (V2) | 비평을 반영한 코드로 개선된 차트 생성 |

### 완료 기준 — 랩 재현

| # | 기준 | 검증 |
|---|---|---|
| 1 | 지시문 하나로 V1·V2 차트 두 장이 생성된다 | `python run.py "지시문"` |
| 2 | 코드가 `<execute_python>` 태그로 감싸여 추출·실행된다 | 추출된 코드 출력 |
| 3 | 비평 단계가 **이미지를 실제로 입력받는다** | 요청 페이로드 로깅 + 비평이 **이미지에만 있는 정보**(축 눈금값·색상)를 언급하는지 |
| 4 | 비평 텍스트와 V2 코드가 한 응답에서 파싱된다 | JSON 첫 줄 + 태그 블록 |
| 5 | **비평이 V1의 실제 결함을 지적한다** | 비평 원문 육안 확인 |
| 6 | **V2가 V1보다 나은 차트다** | 육안 + 객관 체크 (§6) |
| 7 | 중간 산출물이 사용자에게 전부 보인다 | 추출 코드·V1·비평·V2 코드·V2 |
| 8 | `image_basename`으로 실행마다 다른 파일에 저장된다 | 연속 실행 시 덮어쓰기 없음 |

**5·6번이 대표 지표다.** 랩의 학습 성과 문장이 그대로 6번이고, 5번은 그 전제다.

> 5번을 따로 두는 이유: 비평이 헛소리인데 **V2가 우연히 나아지는 경우**가 있다.
> 그러면 결과는 통과지만 반성 패턴을 구현한 것이 아니다.
> 6번만 보면 이 구분이 사라진다.

## 3. 범위

랩 재현이 A, 그 위에 얹는 것이 B다. **A 없이 B를 하지 않는다.**

### A. 랩 재현 (필수)

- 4단계 워크플로우
- `<execute_python>` 태그 기반 코드 추출·실행
- 멀티모달 비평 (이미지 + 원본 코드 입력)
- JSON 첫 줄에서 `feedback` 파싱 + 실패 시 폴백
- `run_workflow()` 대응 — 5개 산출물 반환
- 데이터셋 생성 + `load_and_prepare_data()`
- 생성 모델 / 검토 모델 **파라미터화** (랩의 두 인자)
- **단계별 산출물 표시** — `print_html` 대응 (아래)
- **단계 단독 실행** — 랩의 3.1~3.4 흐름 대응 (아래)

> **`print_html`을 "노트북 전용이라 불필요"로 넘기면 랩의 목적이 깨진다.**
> 랩은 각 단계마다 중간 산출물을 학습자에게 **보여준다** — 추출된 코드, V1 차트,
> 비평 원문, V2 코드, V2 차트. 마크다운 셀도 *"you'll see both the reflection written
> by the LLM and the new code it generated"* 라고 명시한다.
> 노트북 표시 함수는 버리되 **등가물은 남긴다**: 단계별 콘솔 출력 + 산출물 전량 파일 저장.

> **랩은 함수를 하나씩 돌려본 뒤(3.1~3.4) 4장에서 통합한다.**
> 처음부터 통합 파이프라인만 있으면 이 학습 흐름이 사라지므로,
> CLI에 단계 단독 실행 옵션을 둔다 (`--only v1` / `--from-chart <path>`).

### B. 확장 (랩에 없음, A 완료 후)

| # | 확장 | 근거가 되는 레슨 | 우선순위 |
|---|---|---|---|
| B1 | **실행 오류 되먹임** | [01번 §4](../../notes/module-2-reflection/01-reflection-basics.md), [06번 §3](../../notes/module-2-reflection/06-using-external-feedback.md) | 높음 |
| B2 | **V1/V2 객관 채점** | [05번](../../notes/module-2-reflection/05-evaluating-reflection.md) | 중간 |
| B3 | 루브릭 채점 | [05번 §4](../../notes/module-2-reflection/05-evaluating-reflection.md) | 낮음 |
| B4 | 비평/수정 분리 실험 | 모듈 1 [회고](../../notes/retrospectives/research-agent-vs-official.md) | 낮음 |

**B1이 가장 값어치가 크다.** 랩의 프롬프트는 `date` 컬럼 타입 오류를 막으려고
**"CRITICAL", "NEVER do", "ALWAYS"로 같은 경고를 세 번 반복한다.** 실행 오류를 되먹이는
구조라면 프롬프트로 방어할 필요가 없다. 프롬프트만으로 버티다 정체기에 도달한 모습이며
[06번 노트](../../notes/module-2-reflection/06-using-external-feedback.md)의 빨간 곡선이다.

B4는 **기본값이 아니다.** 랩은 비평과 수정을 한 호출로 합쳤고 그 JSON 파싱이 학습 포인트다.
분리는 플래그로만 제공해 두 방식을 비교한다.

### 제외

| 제외 항목 | 이유 |
|---|---|
| 노트북 UI 렌더링 (HTML 표) | CLI 콘솔 출력 + 파일 저장으로 대체. **표시 자체는 버리지 않는다** (§3 A) |
| 프레임워크 | [CLAUDE.md](../../CLAUDE.md) 하드 제약 |
| 쌍대비교 LLM 판정 | [05번 노트](../../notes/module-2-reflection/05-evaluating-reflection.md)가 위치 편향을 경고 |
| 배치 실행·통계 | 랩 범위 밖. [05번 노트](../../notes/module-2-reflection/05-evaluating-reflection.md) 소재이지 04번 소재가 아니다 |

## 4. 랩 명세 상세

충실도의 근거. HTML에서 확인한 계약을 그대로 옮긴다.

### 4.1. `generate_chart_code(instruction, model, out_path_v1) -> str`

프롬프트의 필수 요소:

- 역할 지정 — *"You are a data visualization expert"*
- **출력 형식 강제** — `<execute_python>` 태그 안에만, 설명 금지
- **DataFrame 스키마 9개 컬럼을 프롬프트에 주입** ← 핵심 기법
- 요구사항 8개 — `df` 기존재 가정, matplotlib, 제목·축 레이블·범례, `dpi=300` 저장,
  `plt.show()` 금지, `plt.close()` 호출, import 포함, `date` 타입 주의

> **스키마 주입이 왜 핵심인가:** 모델은 CSV를 볼 수 없다. 컬럼명·타입·이미 계산된
> 파생 컬럼(`quarter`, `month`, `year`)을 알려주지 않으면 존재하지 않는 컬럼을 쓰거나
> 직접 파싱을 시도한다. 이 프롬프트 블록이 곧 **도구 없는 형태의 컨텍스트 주입**이다.

### 4.2. 코드 추출·실행

```python
match = re.search(r"<execute_python>([\s\S]*?)</execute_python>", code_v1)
if match:
    initial_code = match.group(1).strip()
    exec_globals = {"df": df}
    exec(initial_code, exec_globals)
```

`df`만 전역에 주입한다. 코드는 파일을 읽지 않는다.

> **`exec_globals`에 `df` 하나뿐인 것이 요구사항 7·"Don't assume any imports"의 이유다.**
> 실행 컨텍스트에 `pd`도 `plt`도 없으므로 생성 코드가 import를 전부 스스로 해야 한다.
> subprocess로 옮기면 이 제약은 자동으로 지켜지지만, **`df` 주입 방식이 달라진다** —
> 프로세스 경계를 넘길 수 없으므로 자식 프로세스가 CSV를 재로드한다.

> **subprocess로 옮기면 세 가지가 따라온다** (1단계 완료 후 예행으로 확인):
> 프로젝트 루트를 `sys.path`에 주입해야 `chart_agent`가 임포트되고,
> CSV·차트 경로는 **절대 경로**여야 하며,
> `MPLBACKEND=Agg`를 env로 강제해야 GUI 백엔드에 의존하지 않는다.
> 셋 다 랩 프롬프트를 고치지 않고 처리할 수 있어 충실도는 유지된다.

### 4.2-2. 실행 단계를 하드코딩하는 것은 랩의 명시적 설계 결정이다

> *"The chart execution steps are intentionally **hard-coded** to run right after code
> generation/refinement. This mirrors the workflow in the lecture and ensures you see
> each draft's output before moving on."*

즉 **모델은 "언제 실행할지"를 정하지 않는다.** 실행 시점은 코드가 정한다.
[02번 노트의 자율성 스펙트럼](../../notes/module-1-agentic-workflows/02-degrees-of-autonomy.md)에서
모듈 1 리서치 에이전트보다도 낮은 위치다 — 거기서는 최소한 도구 선택이 모델 몫이었다.

이것을 "덜 발전된 설계"로 보면 안 된다. **반성 패턴만 격리해서 관찰하려는 의도적 선택**이고,
학습자가 매 초안의 출력을 반드시 보게 만드는 장치이기도 하다.
따라서 이 프로젝트도 실행 시점을 모델에게 넘기지 않는다.

### 4.3. `reflect_on_image_and_regenerate(...) -> (feedback, refined_code)`

| 요소 | 내용 |
|---|---|
| 입력 | 차트 이미지(base64), 지시문, 모델명, V2 저장 경로, **V1 코드** |
| 출력 형식 | 1행: `{"feedback": "..."}` JSON → 개행 → `<execute_python>` 블록 |
| 파싱 | 첫 줄 `json.loads` → 실패 시 본문에서 첫 `{...}` 재시도 → 그래도 실패 시 오류 메시지를 feedback에 담음 |
| provider 분기 | 모델명에 `claude`/`anthropic` 포함 여부로 라우팅 |
| 제약 | seaborn 금지, `df` 기존재, `dpi=300`, `plt.close()`, import 전부 포함 |

**V1 코드를 함께 넣는 것**이 중요하다. 이미지만 보면 "왜 이렇게 그려졌는지"를 모른다.

> ⚠ **랩 산문이 또 프롬프트와 어긋난다.** 설명 셀은 *"we require two fields: `feedback` …
> `refined_code`"* 라고 하지만, 프롬프트는 JSON에 **`feedback` 하나만** 요구하고
> (*"a valid JSON object with ONLY the 'feedback' field"*) 코드는 JSON 밖 태그로 받는다.
> 폴백 dict의 `"refined_code": ""` 는 이전 설계의 **잔재(죽은 키)** 다 — 아무도 읽지 않는다.
>
> 계약은 프롬프트를 따르고, **죽은 키는 재현하지 않는다.** 파싱 결과는 `feedback` 문자열
> 하나 + 태그에서 뽑은 코드다. 이 모순 자체는 회고에 기록한다.

### 4.4. `run_workflow(...) -> dict`

반환 계약:

```python
{"code_v1", "chart_v1", "feedback", "code_v2", "chart_v2"}
```

파라미터: `dataset_path`, `user_instructions`, `generation_model`,
`reflection_model`, `image_basename`.

> 랩이 명시적으로 강조한 것 — *"Remember to also adjust the `image_basename` so each run
> saves its results under a new filename"*. 실행마다 결과가 덮어써지면 비교가 불가능하다.

### 4.5. 랩이 권장한 실험

- 지시문 바꿔보기
- **모델 조합 바꿔보기** — 생성은 빠른 모델, 검토는 추론 모델
- 랩 예시: 생성 `gpt-4o-mini` / 검토 `o4-mini` 또는 `claude-sonnet-4-6`

이 실험 가능성이 설계 요구사항이다. 모델명을 하드코딩하지 않는다.

## 5. 설계 결정과 근거

| 결정 | 선택 | 근거 |
|---|---|---|
| 실행 형태 | CLI 모듈 + 단계 단독 실행 | 반복 실행·버전 관리. 랩의 단계별 실습 흐름은 옵션으로 보존 |
| 코드 실행 | **subprocess + 타임아웃** | 랩의 인라인 `exec`는 예외 시 중단되고 stderr를 못 잡는다. B1의 전제 |
| 비평/수정 | **랩대로 한 호출** (분리는 플래그) | JSON 파싱이 랩의 학습 포인트 |
| 생성 모델 | `openai:gpt-4.1-mini` | 랩의 `gpt-4o-mini` 대응. 현행 모델 ID ([CLAUDE.md](../../CLAUDE.md)) |
| 검토 모델 | `openai:gpt-5` **기본** | 랩 기본값이 OpenAI(`o4-mini`)다. Anthropic은 랩에서도 주석 처리된 대안 |
| Anthropic 경로 | `--reflect-model anthropic:claude-sonnet-5` | 랩의 주석 처리된 선택지. **provider 라우팅 검증에 필요** |

> 검토 모델 기본을 Anthropic으로 잡으면 랩과 달라지고, `ANTHROPIC_API_KEY`가 없는
> 환경에서 바로 실패한다. **기본은 OpenAI, Anthropic은 옵션**이 맞다.
> 다만 두 provider의 이미지 형식이 다르므로(아래) 라우팅 검증은 반드시 양쪽으로 한다.
| 이미지 입력 | **provider별 직접 구성** | aisuite가 이미지를 정규화하지 않음 (아래) |
| 데이터셋 | 시드 고정 생성기 | 재현성 |

### aisuite를 이미지에 쓰지 않는 근거

| provider | aisuite가 하는 일 |
|---|---|
| OpenAI | [`message_converter.py`](../../venv/lib/python3.12/site-packages/aisuite/providers/message_converter.py) — dict를 **그대로 통과** → OpenAI 형식 이미지 블록 동작 |
| Anthropic | [`anthropic_provider.py`](../../venv/lib/python3.12/site-packages/aisuite/providers/anthropic_provider.py)의 `_convert_dict_message()` — `content`를 **그대로 통과**. OpenAI 형식(`image_url`)을 Anthropic 형식(`source.base64`)으로 **변환하지 않는다** |

즉 aisuite는 이미지에 관해 아무 일도 하지 않는다. 랩이 `image_openai_call`과
`image_anthropic_call`을 따로 둔 이유가 이것이다.
**텍스트는 aisuite, 이미지는 provider 라우팅**으로 나눈다.

### 데이터셋

랩 출력 표본에서 읽은 스키마:

```
date        2024-12-05    (datetime64)
time        09:18         (문자열 HH:MM — date와 문자열 결합 금지)
cash_type   card | cash
card        ANON-0000-0000-0141
price       1.812 (Espresso) · 2.596 (Cortado) · 3.282·3.576 (Latte)
quarter month year        파생 정수 컬럼
```

`coffee_name`은 **슬라이드 V2 범례에서 8종을 확정할 수 있다** —
Americano · Americano with Milk · Cappuccino · Cocoa · Cortado · Espresso ·
Hot Chocolate · Latte. 랩 V1 코드가 `inner join`을 쓰므로
**두 해 모두에 8종이 다 있어야** 하나도 누락되지 않는다.

### ⚠ 수량 컬럼이 없다 — 각 행이 거래 1건이다

랩 3.1의 산문은 스키마를 다르게 적어놨다.

> *"The dataset includes fields such as `date`, `coffee_type`, `quantity`, and `revenue`"*

> **주의: "프롬프트에 없다"만으로는 근거가 안 된다.** 프롬프트는 모델에게 *알려줄 것*을
> 고른 목록이지 스키마 전체라는 보장이 없다. 산문과 프롬프트가 어긋난다는 사실만으로는
> 어느 쪽이 낡았는지도 가릴 수 없다.

**결정적 근거는 `df.sample(n=5)`의 렌더링 결과다** — 프롬프트가 아니라 실제 DataFrame이
출력된 것이고, `labs/module-2/M2_UGL_1.html`의 `<table>`에서 확인된다.

```
헤더 9개  : date · time · cash_type · card · price · coffee_name · quarter · month · year
데이터 행 : 전부 9개 셀
생략 표시 : 없음        ← pandas가 컬럼을 접은 게 아니다
```

보강 근거 둘:

- `price`가 2.596 / 3.576 / 1.812 — **잔당 단가**다. 수량이 있었다면 매출은
  `price × quantity`인데, V1 코드는 `groupby('coffee_name')['price'].sum()` 결과에
  y축 "Total Sales ($)"를 붙인다. **수량이 항상 1일 때만 이 합계가 매출이 된다.**
- `card`가 `ANON-0000-0000-0141` 같은 익명 결제 ID다. 자판기 **거래 단위** 데이터다.

따라서 데이터 생성기의 제약이 확정된다.

| | |
|---|---|
| 한 행의 의미 | **거래 1건** = 1잔 |
| "sales" 계산 | `price` **합계** 또는 행 수(count) |
| 판매량 차이를 만드는 법 | **행 수를 늘린다** (`quantity` 컬럼을 만들지 않는다) |

### 가격 인상이 Q1 비교에 섞여 든다

랩 표본에서 Latte가 2024-07 **3.282** → 2024-12 **3.576**이다. 같은 음료의 가격이
올랐다는 뜻이라 `PRICE_RISE_DATE = 2024-10-01`로 모델링했고, 관측값 5개가 전부 맞는다.

**부작용이 있다.** Q1 2024는 전부 인상 전, Q1 2025는 전부 인상 후다.
따라서 "Total Sales ($)" 비교는 물량과 단가를 섞는다.

```
매출 1.86배  =  물량 1.71배  ×  단가 1.09배
```

**그래도 없애지 않는다.** 관측 증거가 강제하는 성질이고, 원본 데이터도 같았을 것이다.
오히려 비평 단계가 이걸 짚어내는지가 관찰 지점이 된다 —
[05번 노트](../../notes/module-2-reflection/05-evaluating-reflection.md)의 루브릭
"비교가 공정한가" 항목에 실질적 근거가 생긴다.

> **[UNCERTAIN]** 원본 **CSV 파일**에 `quantity`가 있는지는 확인할 수 없다.
> `load_and_prepare_data()`가 컬럼을 버렸을 가능성이 남는다.
> 다만 **설계에는 영향이 없다** — 맞춰야 할 계약은 CSV가 아니라
> `load_and_prepare_data()`가 **반환하는 df**이고, 그것은 9컬럼으로 확정됐다.
> 생성 코드는 df만 본다.

**기간은 2024-01-01 ~ 2025-03-31로 잡는다.** 지시문이 Q1 2024 vs Q1 2025 비교이므로
양쪽 분기가 온전히 있어야 랩이 의도한 비교가 성립한다.

> `time`·`cash_type`·`card`는 이 지시문에 쓰이지 않는다. 그래도 넣는다 —
> 랩 프롬프트가 **9컬럼 전부를 주입**하고, 그중 관련된 것만 모델이 골라내는 것이
> 과제의 일부이기 때문이다. 안 쓰는 컬럼을 빼면 스키마 주입 기법이 시시해진다.

> **[UNCERTAIN]** 원본 데이터가 2024년 3월부터 시작해 Q1 2024가 한 달뿐일 가능성이 있다.
> 표본 5행에 Q1 2024가 없다는 것이 유일한 단서이고, 반대로 랩의 V1 출력은 `inner join`
> 후 두 해 모두 막대가 그려졌으므로 Q1 2024 데이터가 존재한다는 정황이 더 강하다.
> 확인할 수 없으므로 **기본 데이터셋은 양쪽 분기를 온전히 채운다.**
> 기간이 불균형할 때 비평이 이를 잡아내는지는 `--partial-q1` 플래그로 따로 실험한다.

## 6. 평가 설계

**A 단계에서는 육안 확인이 기준이다.** 랩도 그렇게 한다.
아래는 B2·B3에 해당하며, A가 끝난 뒤 붙인다.

### 6.1. 객관 — Figure 내성 검사 (B2)

강의는 "제목이 있는가"를 LLM에게 묻지만, 차트를 우리가 실행하므로 **Figure 객체에 직접
물어볼 수 있다.** `plt.savefig`를 감싸 저장 직전 상태를 JSON으로 덤프한다.

| 체크 | 판정 | 근거 |
|---|---|---|
| 실행 성공 | 종료 코드 0 | — |
| 제목 존재 | `ax.get_title() != ""` | 랩 프롬프트 요구사항 3 |
| x/y축 레이블 | `get_xlabel()` / `get_ylabel()` | 랩 프롬프트 요구사항 3 |
| 범례 존재 | `ax.get_legend() is not None` | 랩 프롬프트 요구사항 3 |
| dpi=300 저장 | `savefig` 인자 캡처 | 랩 프롬프트 요구사항 4 |
| 데이터 계열 수 ≥ 2 | `len(ax.containers)` | 비교 질문일 때 |
| **계열이 시각적으로 구분되는가** | 누적(`bottom` 지정) 또는 오프셋 없는 동일 x 위치 검출 | V1의 결함 (아래) |

앞 5개는 **랩 프롬프트가 명시한 요구사항을 그대로 체크**하는 것이다.
모델이 지시를 지켰는지 코드로 확인한다.

> ~~눈금 레이블 겹침 검출~~ — 제외. 회전각과 문자열 길이만으로는 판정할 수 없다.
> 렌더러 없이 텍스트 실제 폭을 알 수 없다.

### V1의 결함은 실행마다 다르다

확보한 두 자료의 V1이 **서로 다르다.**

| 출처 | V1 차트 | 결함 |
|---|---|---|
| 강의 슬라이드 (`plot.png`) | x축 = 연도, 음료 8종을 **누적(stacked)** | 연도 총합만 보이고 음료별 비교 불가 |
| 랩 노트북 실행 출력 | x축 = 음료명, 두 해를 같은 위치에 **겹쳐 그림** | 짧은 막대가 가려짐 |

```python
# 랩 노트북이 실제로 생성한 V1 — 오프셋 없이 같은 x에 두 번
plt.bar(comparison['coffee_name'], comparison['price_2024'], label='2024', alpha=0.6)
plt.bar(comparison['coffee_name'], comparison['price_2025'], label='2025', alpha=0.6)
```

같은 프롬프트인데 결함 종류가 다르다. **LLM 출력이 비결정적이기 때문이다.**

따라서 **특정 결함을 하드코딩해 채점하지 않는다.** `"막대가 겹치는가"`가 아니라
`"두 계열이 시각적으로 구분되는가"`로 판정하면 누적과 겹침이 똑같이 걸린다.

공통점은 하나다 — **둘 다 문법적으로 멀쩡하고, 그림을 봐야 결함이 보인다.**
[03번 노트](../../notes/module-2-reflection/03-chart-generation-workflow.md)가 말한 지점이다.
V2는 양쪽 다 분리된 그룹 막대로 수렴한다.

### 6.2. 주관 — 루브릭 (B3)

내성 검사로 안 되는 것만 남긴다: 차트 유형 적절성, 색상 구분 명확성.

[05번 노트](../../notes/module-2-reflection/05-evaluating-reflection.md)의 규칙:
**1~5점 척도 금지(이진 합산), 쌍대비교 금지(위치 편향), 채점 모델 분리.**

## 7. 리스크

| 리스크 | 영향 | 대응 |
|---|---|---|
| **LLM 생성 코드 실행** | 임의 코드 실행 | subprocess + 타임아웃 + 작업 디렉터리 격리. ⚠ **진짜 샌드박스가 아니다**(seccomp 없음). 로컬 학습 한정 |
| 무한 루프·거대 플롯 | 프로세스 행 | 타임아웃 30초 후 kill |
| pandas 3.0.5 비호환 | 랩은 2.x 가정 가능성 | [CLAUDE.md](../../CLAUDE.md) 경고 항목. 1단계에서 먼저 검증 |
| JSON 파싱 실패 | 비평 유실 | 랩과 같은 3단 폴백. 최종 실패도 **기록은 남긴다** |
| 되먹임 루프 미종료 | 같은 오류 반복 | 재시도 2회 상한. 초과 시 실패로 기록 (조용한 무시 금지) |
| 이미지 API 비용 | 1회 실행 = 텍스트 1 + 이미지 1~2 | 이미지 호출이 비싸다. 반복 실험 시 지시문 고정 |

## 8. 비목표

- 프로덕션 수준 샌드박싱 (컨테이너·seccomp)
- 노트북 UI 재현
- 배치 실행 통계 — [05번 레슨](../../notes/module-2-reflection/05-evaluating-reflection.md) 소재이지 이 랩 소재가 아니다
- 모듈 1 코드와의 공통 모듈 추출 — §9 참고

## 9. 완성 후 계획

1. **A 완료 시점에 V1/V2 육안 비교** — 랩의 완료 조건
2. B1(오류 되먹임)이 실제로 발동한 사례 수집 — 몇 건을 구제했는가
3. 비평이 **V1의 결함**(누적이든 겹침이든)을 지적했는지 확인 — §2 완료 기준 5번
4. 모듈 1 리서치 에이전트와의 코드 중복 검토.
   지금 미리 공통 모듈을 뽑지 않는 이유: 사례가 1.5개뿐이고 성급한 추상화가 더 나쁘다
5. 회고를 `notes/retrospectives/`에 기록
