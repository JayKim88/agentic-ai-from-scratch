# 차트 에이전트 — 기획서

> DeepLearning.AI *Agentic AI* 모듈 2 ungraded 랩 "Chart Generation" 자체 구현.
> 작성 2026-08-04

이 문서는 **무엇을 만들 것인가**만 담는다.
발견·시행착오는 [회고](../../notes/retrospectives/chart-agent-lab-findings.md)에 있다.

## 1. 배경

랩 자료를 확보했으므로 백지 설계가 아니라 **명세가 있는 구현**이다.

| 자료 | 상태 |
|---|---|
| [`M2_UGL_1.html`](../../labs/module-2/M2_UGL_1.html) | 코드 셀 25 · 마크다운 20. 함수 4개와 프롬프트 전문 |
| [`coffee_sales.csv`](../../labs/module-2/coffee_sales.csv) | 3,636행, 2024-03-01 ~ 2025-03-23 |
| [`chart_v1.png`](../../labs/module-2/chart_v1.png) · [`chart_v2.png`](../../labs/module-2/chart_v2.png) | 랩의 실제 산출물 |
| `utils.py` | ⏸ **의도적으로 열지 않음.** 3단계 `vision.py`의 정답지다 |

`utils.py`를 열지 않고 호출부에서 읽어낸 계약:

```
load_and_prepare_data(path)          → DataFrame
get_response(model, prompt)           → str
encode_image_b64(path)                → (media_type, b64)
image_openai_call(model, prompt, media_type, b64)    → str
image_anthropic_call(model, prompt, media_type, b64) → str
ensure_execute_python_tags(body)      → str
print_html(content, title, is_image)  → 노트북 표시
```

## 2. 목표

> *"By the end of this lab, you will have implemented the reflection pattern in code
> and used it to improve a data visualization."*

**멀티모달 LLM이 생성된 차트를 보고 비평한 뒤 코드를 고쳐 더 나은 차트를 만든다.**

### 랩이 정의한 4단계

| # | 단계 |
|---|---|
| 1 | V1 코드 생성 |
| 2 | 실행 → 차트 |
| 3 | **코드와 차트를 함께** 평가 |
| 4 | 개선된 코드 생성 → 실행 |

### 완료 기준

| # | 기준 | 검증 |
|---|---|---|
| 1 | 지시문 하나로 V1·V2 두 장 생성 | `python run.py "지시문"` |
| 2 | `<execute_python>` 태그로 추출·실행 | 추출된 코드 출력 |
| 3 | 비평 단계가 **이미지를 실제로 입력받음** | 요청 페이로드 로깅 + 비평이 이미지에만 있는 정보(축 눈금값·색상)를 언급하는지 |
| 4 | 비평과 V2 코드가 한 응답에서 파싱됨 | JSON 첫 줄 + 태그 블록 |
| 5 | **비평이 V1의 실제 결함을 지적함** | 비평 원문 육안 확인 |
| 6 | **V2가 V1보다 나은 차트** | 육안 + 객관 체크 (§6) |
| 7 | 중간 산출물이 전부 보임 | 추출 코드·V1·비평·V2 코드·V2 |
| 8 | `image_basename`으로 덮어쓰기 없음 | 연속 실행 |

**5·6번이 대표 지표다.** 5번을 따로 두는 이유: 비평이 헛소리인데 **V2가 우연히 나아지면**
결과는 통과지만 반성 패턴을 구현한 것이 아니다.

## 3. 범위

**A 없이 B를 하지 않는다.**

### A. 랩 재현 (필수)

- 4단계 워크플로우
- `<execute_python>` 태그 추출·실행
- 멀티모달 비평 (이미지 + V1 코드 입력)
- JSON 첫 줄에서 `feedback` 파싱 + 폴백
- `run_workflow()` — 5개 산출물 반환
- 생성 모델 / 검토 모델 파라미터화
- **단계별 산출물 표시** (`print_html` 대응)
- **단계 단독 실행** (랩 3.1~3.4 흐름)

> `print_html`을 "노트북 전용"으로 넘기면 랩의 목적이 깨진다. 랩은 매 단계 중간 산출물을
> 학습자에게 **보여준다** — *"you'll see both the reflection written by the LLM and the new
> code it generated"*. HTML 렌더링은 버리되 **표시는 남긴다**: 콘솔 출력 + 파일 저장.

### B. 확장 (A 완료 후)

| # | 확장 | 근거 | 우선순위 |
|---|---|---|---|
| B1 | 실행 오류 되먹임 | [01번](../../notes/module-2-reflection/01-reflection-basics.md) · [06번](../../notes/module-2-reflection/06-using-external-feedback.md) | 높음 |
| B2 | V1/V2 객관 채점 | [05번](../../notes/module-2-reflection/05-evaluating-reflection.md) | 중간 |
| B3 | 루브릭 채점 | [05번](../../notes/module-2-reflection/05-evaluating-reflection.md) | 낮음 |
| B4 | 비평/수정 분리 실험 | 모듈 1 [회고](../../notes/retrospectives/research-agent-vs-official.md) | 낮음 |

B4는 **기본값이 아니다.** 랩은 한 호출로 합쳤고 그 JSON 파싱이 학습 포인트다.

### 제외

| 항목 | 이유 |
|---|---|
| 노트북 HTML 렌더링 | 콘솔 + 파일로 대체 |
| 프레임워크 | [CLAUDE.md](../../CLAUDE.md) 하드 제약 |
| 쌍대비교 LLM 판정 | 위치 편향 ([05번](../../notes/module-2-reflection/05-evaluating-reflection.md)) |
| 배치 실행·통계 | 05번 레슨 소재이지 04번 소재가 아니다 |

## 4. 랩 명세

충실도의 근거. HTML에서 확인한 계약이다.

### 4.1. `generate_chart_code(instruction, model, out_path_v1) -> str`

- 역할 지정 — *"You are a data visualization expert"*
- 출력 형식 강제 — `<execute_python>` 태그 안에만, 설명 금지
- **DataFrame 스키마 9컬럼 프롬프트 주입** ← 핵심 기법
- 요구사항 8개 — `df` 기존재, matplotlib, 제목·축 레이블·범례, `dpi=300`,
  `plt.show()` 금지, `plt.close()`, import 포함, `date` 타입 주의

> **스키마 주입이 왜 핵심인가:** 모델은 CSV를 볼 수 없다. 컬럼명·타입·이미 계산된
> 파생 컬럼을 알려주지 않으면 없는 컬럼을 쓰거나 직접 파싱을 시도한다.

### 4.2. 코드 추출·실행

```python
match = re.search(r"<execute_python>([\s\S]*?)</execute_python>", code_v1)
if match:
    exec(match.group(1).strip(), {"df": df})
```

`df`만 전역에 주입한다 — 그래서 생성 코드가 import를 스스로 해야 한다.

**실행 시점은 랩이 명시적으로 하드코딩했다.**

> *"The chart execution steps are intentionally hard-coded to run right after code
> generation/refinement. … ensures you see each draft's output before moving on."*

모델은 "언제 실행할지"를 정하지 않는다. [자율성 스펙트럼](../../notes/module-1-agentic-workflows/02-degrees-of-autonomy.md)에서
모듈 1보다도 낮다 — 반성 패턴만 격리해 관찰하려는 의도적 선택이므로 그대로 따른다.

subprocess 전환에 따르는 것은 [`executor.py` 독스트링](chart_agent/executor.py)에 있다.

### 4.3. `reflect_on_image_and_regenerate(...) -> (feedback, refined_code)`

| 요소 | 내용 |
|---|---|
| 입력 | 이미지(base64), 지시문, 모델명, V2 경로, **V1 코드** |
| 출력 | 1행 `{"feedback": "..."}` JSON → 개행 → `<execute_python>` 블록 |
| 파싱 | 첫 줄 `json.loads` → 실패 시 본문 첫 `{...}` → 실패 메시지를 feedback에 |
| provider 분기 | 모델명에 `claude`/`anthropic` 포함 여부 |
| 제약 | seaborn 금지, `df` 기존재, `dpi=300`, `plt.close()`, import 포함 |

**V1 코드를 함께 넣는 것**이 중요하다. 이미지만 보면 왜 그렇게 그려졌는지 모른다.

JSON에서는 **`feedback` 하나만** 파싱한다. 랩 폴백 dict의 `refined_code` 키는
아무도 읽지 않는 잔재다 ([회고 §2](../../notes/retrospectives/chart-agent-lab-findings.md)).

### 4.4. `run_workflow(...) -> dict`

```python
{"code_v1", "chart_v1", "feedback", "code_v2", "chart_v2"}
```

파라미터: `dataset_path`, `user_instructions`, `generation_model`,
`reflection_model`, `image_basename`.

> *"Remember to also adjust the `image_basename` so each run saves its results under a
> new filename"* — 덮어써지면 비교가 불가능하다.

### 4.5. 랩이 권장한 실험

지시문 바꾸기, **모델 조합 바꾸기** (생성은 빠른 모델, 검토는 추론 모델).
모델명을 하드코딩하지 않는 것이 설계 요구사항이다.

## 5. 설계 결정

| 결정 | 선택 | 근거 |
|---|---|---|
| 실행 형태 | CLI + 단계 단독 실행 | 반복 실행·버전 관리. 랩의 단계별 실습은 옵션으로 보존 |
| 코드 실행 | subprocess + 타임아웃 + `-I` | 인라인 `exec`는 예외 시 중단되고 stderr를 못 잡는다 |
| df 전달 | **pickle** | dtype 보존. CSV 왕복은 9컬럼 계약을 두 군데로 쪼갠다 |
| 실행 실패 (A) | **중단.** 재시도 없음 | 차트가 없으면 비평이 성립하지 않는다. 재시도는 B1 |
| 비평/수정 | 랩대로 한 호출 (분리는 플래그) | JSON 파싱이 랩의 학습 포인트 |
| 생성 모델 | `openai:gpt-4.1-mini` | 랩의 `gpt-4o-mini` 대응 |
| 검토 모델 | `openai:gpt-5` 기본 | 랩 기본값이 OpenAI. Anthropic은 랩에서도 주석 처리된 대안 |
| 이미지 입력 | provider별 직접 구성 | aisuite가 이미지를 정규화하지 않음 (아래) |

### aisuite를 이미지에 쓰지 않는 근거

| provider | aisuite가 하는 일 |
|---|---|
| OpenAI | dict를 **그대로 통과** → OpenAI 형식 블록 동작 |
| Anthropic | `content`를 **그대로 통과**. `image_url`을 `source.base64`로 **변환하지 않음** |

즉 aisuite는 이미지에 관해 아무 일도 하지 않는다. 랩이 `image_openai_call`과
`image_anthropic_call`을 따로 둔 이유다. **텍스트는 aisuite, 이미지는 provider 라우팅.**

### 데이터셋

`resolve_dataset_path()`가 랩 파일을 우선 쓰고, 없으면 자체 생성기 산출물로 폴백한다.

```
date        2024-03-01    (datetime64[us])
time        06:14         (문자열 HH:MM — date와 결합 금지)
cash_type   card | cash
card        ANON-0000-0000-0001
price       음료·시기별 6단계
coffee_name 8종
quarter month year        로더가 파생
```

| 제약 | 내용 |
|---|---|
| **수량 컬럼 없음** | 1행 = 거래 1건. 판매량은 `price` 합계나 행 수 |
| **Q1 2024 = 3월뿐** | 206행 vs Q1 2025 943행. 결과 해석 시 유의 |
| inner join 안전 | 랩 V1이 `coffee_name`으로 조인하므로 8종이 두 Q1에 다 있어야 한다 |

## 6. 평가 설계

**A 단계 기준은 육안 확인이다.** 랩도 그렇게 한다. 아래는 B2·B3다.

### 6.1. 객관 — Figure 내성 검사 (B2)

`plt.savefig`를 감싸 저장 직전 상태를 JSON으로 덤프한다.

| 체크 | 판정 | 근거 |
|---|---|---|
| 실행 성공 | 종료 코드 0 + 파일 존재 | — |
| 제목 존재 | `ax.get_title() != ""` | 랩 요구사항 3 |
| x/y축 레이블 | `get_xlabel()` / `get_ylabel()` | 랩 요구사항 3 |
| 범례 존재 | `ax.get_legend() is not None` | 랩 요구사항 3 |
| dpi=300 | `savefig` 인자 캡처 | 랩 요구사항 4 |
| **지시문 충족** | 지시문이 요구한 비교 차원이 차트에 남아 있는가 | ⚠ 아래 |
| 계열 구분 | 누적(`bottom`) 또는 오프셋 없는 동일 x 위치 | 퇴행 검출 |

앞 5개는 **랩 프롬프트가 명시한 요구사항을 코드로 되받아 확인**하는 것이다.

> ⚠ **"지시문 충족"이 가장 중요하다.** 랩의 실물 V2는 연도 비교를 잃고도
> 제목·축·범례·dpi를 다 갖춰 **나머지 항목에서 만점을 받는다.**
> 상세: [회고 §1](../../notes/retrospectives/chart-agent-lab-findings.md)

> ~~눈금 레이블 겹침~~ — 제외. 렌더러 없이 텍스트 실제 폭을 알 수 없다.

### 6.2. 주관 — 루브릭 (B3)

내성 검사로 안 되는 것만: **차트 유형 적절성, 색상 구분 명확성.**

규칙 ([05번 노트](../../notes/module-2-reflection/05-evaluating-reflection.md)):
1~5점 척도 금지(이진 합산), 쌍대비교 금지(위치 편향), 채점 모델 분리.

> "비교 공정성"은 넣지 않는다. 비평 모델은 이미지와 V1 코드만 보므로 데이터 범위를
> 알 수 없다 — **탐지 불가능한 것을 채점하면** 항상 실패하는 나쁜 eval이 된다.

## 7. 리스크

| 리스크 | 대응 |
|---|---|
| **LLM 코드 실행** | subprocess + 타임아웃 + `-I`. ⚠ **샌드박스가 아니다**(seccomp 없음). 로컬 학습 한정 |
| 무한 루프 | 타임아웃 30초 후 종료 |
| JSON 파싱 실패 | 랩과 같은 3단 폴백. 최종 실패도 **기록은 남긴다** |
| 되먹임 미종료 (B1) | 재시도 2회 상한. 초과 시 실패로 기록 |
| 이미지 API 비용 | 1회 실행 = 텍스트 1 + 이미지 1~2. 반복 실험 시 지시문 고정 |

## 8. 비목표

- 프로덕션 샌드박싱 (컨테이너·seccomp)
- 노트북 UI 재현
- 배치 실행 통계 — 05번 레슨 소재
- 모듈 1 코드와의 공통 모듈 추출 — §9

## 9. 완성 후

1. A 완료 시점에 V1/V2 육안 비교
2. B1이 실제로 발동한 사례 수집
3. **`utils.py` 대조** — 3단계 `vision.py`와 비교
4. 모듈 1과의 코드 중복 검토. 사례가 1.5개뿐이라 지금 추상화하지 않는다
5. [회고](../../notes/retrospectives/chart-agent-lab-findings.md) 갱신
