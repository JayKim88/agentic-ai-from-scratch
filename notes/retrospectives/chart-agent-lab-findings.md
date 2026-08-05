# 차트 에이전트 — 랩 대조 기록

> 모듈 2 ungraded 랩 "Chart Generation"을 재현하며 발견한 것들.
> 진행 중인 문서다. 프로젝트: [projects/chart-agent](../../projects/chart-agent/README.md)
> 최종 수정 2026-08-05

기획서와 체크리스트는 **무엇을 만들 것인가**만 담는다.
**무엇을 배웠나**는 여기 모은다.

---

## 1. 반성이 차트를 퇴행시킨 실물 사례

랩이 배포한 `chart_v1.png` / `chart_v2.png`를 열어봤다. **예상이 전부 틀렸다.**

| | 예상 | 실물 |
|---|---|---|
| V1 | 누적(슬라이드) 또는 겹침(노트북 코드) | **이미 그룹 막대** |
| V1의 결함 | 계열이 안 나뉨 | **x축 레이블 잘림** + x축 레이블 없음 |
| V2 | 그룹 막대로 수렴 | **누적 막대. 연도 비교가 사라짐** |

```
지시문   : "Q1 coffee sales in 2024 and 2025 비교"
V1 제목  : Q1 Coffee Sales Comparison: 2024 vs 2025   ← 답함
V2 제목  : Quarterly Coffee Sales Breakdown           ← 답하지 않음
```

숫자로 확인했다. V2의 Q1 막대 ≈ 3,660 = **2024년 3월 + 2025년 1~3월 합계**(3,665.10).
연도 차원을 버리고 두 해를 합쳤다.

V2가 고친 것도 있다 — x축 레이블 추가, 잘림 해소, 범례를 밖으로 빼고 제목 추가.
**미관은 개선, 의미는 퇴행이다.**

강의 슬라이드와 정반대다.

```
슬라이드 : V1 누적 → V2 그룹   (개선)
실물     : V1 그룹 → V2 누적   (퇴행)
```

### 이것이 설계에 남긴 것

강의는 "반성이 개선한다"고 말하는데 랩이 배포한 산출물은 퇴행 사례다.
채점 없이 돌렸다면 *"V2가 더 예쁘네"* 하고 넘어갔을 것이다 —
[05번 레슨](../module-2-reflection/05-evaluating-reflection.md)이 필요한 이유의 실물 증거다.

두 가지가 평가 설계에 반영됐다.

1. **"지시문 충족" 검사 추가.** 기존 항목(제목·축·범례·dpi)만으로는 **V2가 만점**을 받는다
2. **"계열 구분" 검사의 용도가 반대.** V1의 결함을 잡으려 만들었는데 실물에서는 V2가 걸린다 — 퇴행 검출용이다

📌 두 파일이 같은 실행에서 나왔는지는 확인할 수 없다(8개월 전 파일).
어느 쪽이든 **"V2가 다른 질문에 답할 수 있다"** 는 사실은 유효하다.

---

## 2. 랩 문서의 불일치 3건

전부 **프롬프트나 코드는 고치고 설명은 안 고친** 흔적으로 보인다.

| # | 위치 | 내용 |
|---|---|---|
| 1 | 노트북 3.1 산문 | *"fields such as `date`, `coffee_type`, `quantity`, `revenue`"* — 실제 스키마엔 셋 다 없다 |
| 2 | 노트북 3.3 산문 | *"we require two fields: `feedback` … `refined_code`"* — 프롬프트는 `feedback` 하나만 요구하고, 폴백 dict의 `refined_code` 키는 아무도 읽지 않는다 |
| 3 | 랩 `README.md` | 다른 버전의 랩을 설명한다 (아래) |

### README가 설명하는 것과 배포본

| 랩 README | 실제 배포본 |
|---|---|
| `visualization.ipynb` | `M2_UGL_1.ipynb` |
| `original_chart.jpg` / `refined_chart.jpg` | `chart_v1.png` / `chart_v2.png` |
| `evaluation_model=` | `reflection_model=` |
| `date (M/D/YY)` | 실제 CSV는 ISO `2024-03-01` |
| **5단계: side-by-side 비교** | 없음 |
| **`logs_*.txt` 피드백 로그** | 없음 |
| `GOOGLE_API_KEY` 필요 | 미사용 |

**쓸모 있는 건 하나다.** 원본 랩에는 **비교와 로그가 있었는데 배포본에서 빠졌다.**
확장(B2·B3)으로 잡은 채점·비교가 사실 원본에 있던 기능이다.

---

## 3. 내가 틀렸던 판단들

### Q1 2024 함정 — 맞는 주장을 스스로 철회했다

처음에 "Q1 2024가 3월뿐인 의도적 함정"이라고 적었다가,
*"랩 V1 출력에 두 해 막대가 다 있으니 Q1 2024 데이터가 존재한다"* 는 이유로 격하했다.

**그 논리가 틀렸다.** 3월에도 8종이 다 있으니 막대는 당연히 두 해 다 그려진다 —
분기가 온전하다는 뜻이 아니다. 실물은 2024-03-01에 시작한다.

| | 행 수 | 개월 | 매출 |
|---|---|---|---|
| Q1 2024 | 206 | **3월만** | 705.02 |
| Q1 2025 | 943 | 1·2·3월 | 2,960.08 |

**4.20배 차이 중 3배는 기간이 3배라서다.**

### 그런데 이것을 평가 항목으로 삼는 것도 틀렸다

한 번 더 정정했다. **비평 모델이 이를 탐지할 방법이 없다** — 보는 것은 이미지와 V1 코드뿐이고
둘 다 데이터 범위를 드러내지 않는다. 탐지 불가능한 것을 채점하면 모델 성능과 무관하게
항상 실패하는 나쁜 eval이 된다.

랩이 명시한 비평 축도 *"chart type, labels, color choices, clarity, readability"* —
시각화 품질이지 데이터 타당성이 아니다.

**결과 해석 시 알아둘 데이터 성질로만 남긴다.**

### `validate_dataset`이 실물을 거부했다

위 판단의 결과로 **"두 Q1이 3개월 온전"** 검사를 넣어뒀는데, 실물이 여기 걸렸다.
랩 코드가 요구하는 게 아니라 **내가 그랬으면 좋겠다고 만든 불변식**이었다. 제거했다.

> 교훈: 불변식은 **의존하는 코드가 실제로 요구하는 것**만 넣는다.
> 랩 V1이 inner join을 쓰니 "8종이 두 Q1에 다 있어야 한다"는 진짜 요구사항이고,
> 분기 길이는 아니었다.

### 관측값 검증이 잘못된 것을 테스트했다

생성기의 가격표를 검증할 때 *"그 날 그 음료 행이 존재하는가"* 를 검사했다.
지터 모델을 바꾸자마자 오탐이 났다 — **특정 행의 존재는 난수 추첨**이지 재현 대상이 아니다.
`_price_of(drink, date)` 로 **가격표 자체**를 검사하도록 고쳤다.

### 실행기를 두 번 설계했다

처음엔 자식 프로세스가 `sys.path`에 프로젝트 루트를 넣고 CSV를 다시 로드했다.
리뷰에서 세 문제가 나왔다.

| 문제 | 내용 |
|---|---|
| 격리해놓고 구멍을 뚫음 | 작업 폴더의 `json.py`가 stdlib을 가림 (재현 확인) |
| 경로 손계산 | `Path(__file__).parents[1]` — 패키지를 옮기면 조용히 깨짐 |
| df 가정 | 자식이 항상 전체 CSV를 읽어, 걸러낸 df를 넘길 방법이 없음 |

**부모의 df를 pickle로 넘기니 셋이 한 번에 사라졌다.** 자식이 pandas 외에 아무것도 안 쓴다.

> 교훈: "문서화"는 문제 4의 해결책이 아니었다. 한계를 인정한 것이었을 뿐이다.
> 제대로 된 답을 찾으니 나머지 둘까지 없어졌다.

---

## 4. V1의 결함은 매번 다르다 — 네 번째 사례

3단계에서 우리 코드로 V1을 생성해보니 **또 다른 결함**이 나왔다.

| 출처 | V1 형태 | 결함 |
|---|---|---|
| 강의 슬라이드 | 누적 막대 | 음료별 비교 불가 |
| 랩 노트북 코드 | 겹친 막대 | 짧은 막대가 가려짐 |
| 랩 실물 `chart_v1.png` | 그룹 막대 | x축 레이블 잘림 |
| **우리 실행** (`gpt-4.1-mini`) | **월별 꺾은선** | **2024가 점 하나** |

같은 지시문, 같은 프롬프트인데 네 번 다 다르다. **특정 결함을 하드코딩해 채점하면 안 된다**는
근거가 하나 더 늘었다.

### 그런데 이 사례가 앞선 판단을 반증한다

§3에서 *"Q1 기간 불균형은 비평 모델이 탐지할 수 없다 — 이미지도 코드도 데이터 범위를
드러내지 않는다"* 고 적었다. **이 차트에서는 드러난다.** Q1 2024가 3월뿐이라
꺾은선이 그려지지 않고 **외톨이 점 하나**로 남았다. 눈에 보인다.

즉 **탐지 가능 여부가 차트 형태에 달렸다.**

| V1 형태 | 기간 불균형이 보이는가 |
|---|---|
| 그룹 막대 (랩 실물) | ❌ 집계돼서 안 보임 |
| 월별 꺾은선 (우리) | ✅ 2024가 점 하나 |

**결론은 그대로다.** 루브릭 고정 항목으로는 여전히 부적합하다 — 형태에 따라 탐지 가능성이
달라지니 점수가 모델 품질이 아니라 **V1이 어떻게 그려졌는지**를 재게 된다.
다만 *"비평이 이걸 짚었는가"* 는 관찰 항목으로 기록할 가치가 있다.

## 5. aisuite가 덮지 않는 것이 하나 더 있었다

이미지 형식이 다르다는 건 예상했다. **토큰 상한 인자 이름도 다르다**는 건 실호출에서 알았다.

```
openai:gpt-5  + max_tokens  → 400 Unsupported parameter:
                              'max_tokens' is not supported with this model.
                              Use 'max_completion_tokens' instead.
```

| | OpenAI | Anthropic |
|---|---|---|
| 토큰 상한 | **선택.** gpt-5는 `max_completion_tokens`, gpt-4.1은 `max_tokens` | **필수** `max_tokens` |

OpenAI에는 **아예 보내지 않기로** 했다. 선택 인자인데 모델 계열마다 이름이 달라서,
보내지 않는 쪽이 계열을 판별하는 것보다 견고하다.

> 교훈: 추상화가 덮는 범위는 문서가 아니라 **실호출로 확인**해야 한다.
> aisuite는 *호출*을 통일하지 *요청 본문*을 통일하지 않는다.

## 6. 단계 단독 실행이 랩의 상태를 재현하지 못했다

`--from-chart` 는 랩의 3.1~3.4 개별 실습 흐름을 옮긴 것인데, **형태만 옮겼다.**

랩의 3.3 셀은 노트북 변수로 `code_v1` 을 갖고 있다. 우리 CLI 는 매번 새 프로세스라
그 상태가 없어서, 그 자리에 `(not available)` 문자열을 넣었다.

Claude 가 두 번 연속 실행 불가능한 코드를 냈다.

```python
df = pd.read_csv('…/coffee_sales.csv') if False else None
# Since df is assumed to exist, we proceed with df directly
q1_2024 = df[(df['year'] == 2024) & …]     # TypeError: 'NoneType' …
```

프롬프트 안에 모순이 있다 — 지시문은 *"coffee_sales.csv 의 데이터를 써라"*,
제약은 *"파일을 읽지 마라"*. **둘 다 랩 원문이다.** 고칠 코드가 있으면 `df` 가 살아 있는
변수라는 게 자명하지만, 없으면 모델이 데이터 로딩부터 새로 쓰려다 충돌한다.

같은 모델·같은 지시문을 전체 워크플로우로 돌리니 통과했다. 원인은 모델이 아니라 우리 쪽이었다.

> 교훈: 이 단계의 출력은 **수정된 코드**다. 고칠 대상을 주지 않으면 수정이 아니라 재생성이고,
> 그건 다른 작업이다. 경고로 덮을 게 아니라 입력을 갖추게 해야 했다.

## 7. 같은 입력에도 비평이 달라진다

`baseline` 의 gpt-5 비평과, 같은 이미지·같은 코드로 다시 돌린 비평이 달랐다.

| | 지적 |
|---|---|
| 1회차 | 통화 형식, 알파벳순 정렬, 45° 눈금 혼잡 |
| 2회차 | **union-sorting 때문에** 알파벳순, **pivot 이 더 깔끔**, y축 단위 |

두 번째가 코드 구현까지 파고든다. **한 번 돌려보고 판단하면 안 된다**는
[05번 레슨](../module-2-reflection/05-evaluating-reflection.md)의 근거다.

## 8. `utils.py` 대조 — 정답지를 열고

랩 재현(A)이 끝난 뒤 열었다. 모듈 1에서 공식 저장소를 완성 전에 열지 않았던 것과 같은 규칙이다.

### ⚠ 랩은 aisuite 를 아예 쓰지 않는다

가장 크게 빗나간 추론이다. `utils.py` 에 `import aisuite` 가 없다.

```python
openai_client = OpenAI(...)
anthropic_client = Anthropic(...)

def get_response(model, prompt):
    if "claude" in model.lower() or "anthropic" in model.lower():
        return anthropic_client.messages.create(...)
    return openai_client.responses.create(...)
```

**텍스트도 이미지도 provider SDK 직접 호출**이고, 라우팅도 손으로 한다.

우리는 *"텍스트는 aisuite, 이미지는 provider 라우팅"* 으로 나눴다. aisuite 가 이미지를
정규화하지 않는다는 관찰은 맞았고 실호출로 검증했지만, **"랩도 같은 결론에 도달했다"**
는 서술은 틀렸다. 랩은 애초에 그 추상화를 쓰지 않았다.

### OpenAI 는 Responses API 를 쓴다

```python
# 랩
openai_client.responses.create(
    input=[{"role": "user", "content": [
        {"type": "input_text",  "text": prompt},
        {"type": "input_image", "image_url": data_url},     # 문자열 하나
    ]}],
)

# 우리 (aisuite → Chat Completions)
{"type": "text",      "text": prompt},
{"type": "image_url", "image_url": {"url": data_url}},      # dict
```

**블록 타입 이름도 이미지 필드 모양도 다르다.** 둘 다 동작하지만 다른 API 다.
"OpenAI 이미지 형식" 이 하나가 아니라는 뜻이기도 하다.

### 블록 순서는 우연히 맞췄다

랩도 **텍스트 → 이미지** 다. 초안에서 Anthropic 만 이미지를 앞에 뒀다가
*"provider 비교에서 형식 외의 변수가 된다"* 는 이유로 통일했는데, 그 수정이
랩의 실제 순서와 같아졌다. 근거는 달랐지만 결과는 맞았다.

### 우리가 놓친 것 — 여러 텍스트 블록

```python
# 랩: 모든 텍스트 블록을 이어붙인다
parts = [b.text for b in (msg.content or []) if getattr(b, "type", None) == "text"]
return "".join(parts).strip()
```

```python
# aisuite: 첫 블록만 읽는다
return Message(content=response.content[0].text, ...)
```

Anthropic 이 텍스트 블록을 여러 개로 나눠 보내면 **우리는 뒤를 잃는다.**
첫 블록이 텍스트가 아니면(thinking 블록 등) `content[0].text` 자체가 깨진다.

지금까지 문제가 없었던 것은 claude-sonnet-5 가 한 블록으로 답했기 때문이다.
**잠재 결함이고, 랩은 방어하고 있다.**

### 랩의 Anthropic 시스템 프롬프트는 자기 사용자 프롬프트와 충돌한다

```python
system=("You are a careful assistant. Respond with a single valid JSON object only. "
        "Do not include markdown, code fences, or commentary outside JSON.")
```

**"JSON 객체 하나만, JSON 밖에는 아무것도"** — 그런데 같은 호출의 사용자 프롬프트는
JSON 한 줄 **다음에** `<execute_python>` 블록을 요구한다. 지시가 정면으로 부딪힌다.

우리는 시스템 프롬프트를 두지 않았다. 결과적으로 Claude 가 코드 블록을 정상적으로
돌려줬다 — 이 경우엔 없는 쪽이 나았다.

### `ensure_execute_python_tags` 는 오적용돼 있다

```python
def ensure_execute_python_tags(text):
    text = re.sub(r"^```(?:python)?\s*|\s*```$", "", text).strip()   # 마크다운 펜스 제거
    if "<execute_python>" not in text:
        text = f"<execute_python>\n{text}\n</execute_python>"          # 없으면 감싸기
    return text
```

**태그를 빼먹은 응답을 복구하려는 함수**다. 그런데 호출부가 이렇다.

```python
m_code = re.search(r"<execute_python>([\s\S]*?)</execute_python>", content)
refined_code_body = m_code.group(1).strip() if m_code else ""      # ← 실패하면 빈 문자열
refined_code = utils.ensure_execute_python_tags(refined_code_body) # ← 빈 문자열을 감쌈
```

정규식이 이미 실패한 뒤에 부르므로 **빈 코드가 태그에 감싸여 나온다.** 그리고 4단계에서
그 빈 코드를 실행해 차트 없이 조용히 끝난다.

우리는 `MissingCodeBlockError` 를 던진다. 랩의 복구 의도는 좋았으나 **연결이 어긋나 있어
작동하지 않는다.** 이 판단은 우리 쪽이 맞았다.

### `make_schema_text` — 만들어두고 쓰지 않는다

```python
def make_schema_text(df):
    return "\n".join(f"- {c}: {dt}" for c, dt in df.dtypes.items())
```

**dtypes 로 스키마를 생성하는 함수가 존재하는데, 두 프롬프트 모두 손으로 쓴 블록을 쓴다.**

"스키마를 자동 생성할까 손으로 쓸까" 를 논의하며 *"괄호 안의 절반이 타입이 아니라 명령이라
dtypes 로는 만들 수 없다"* 고 결론지었는데, **랩도 둘 다 만들어보고 손으로 쓴 쪽을 골랐다.**

### `load_and_prepare_data` 는 검증하지 않는다

```python
df = pd.read_csv(csv_path)
if "date" in df.columns:                          # 없으면 파생 컬럼도 없이 반환
    df["date"] = pd.to_datetime(df["date"], errors="coerce")   # 깨진 날짜는 NaT
    ...
return df
```

프롬프트는 9컬럼을 약속하는데 **로더는 그것을 보장하지 않는다.** 우리는
`SCHEMA_COLUMNS` 불일치 시 `ValueError` 를 던진다.

### 랩의 Anthropic 경로는 DLAI 밖에서 동작하지 않는다

```python
anthropic_client = Anthropic(api_key=anthropic_api_key) if anthropic_api_key else Anthropic()
anthropic_client = Anthropic(base_url="http://jupyter-api-proxy.internal.dlai/rev-proxy/anthropic")
```

**두 번째 줄이 첫 줄을 덮어쓰면서 api_key 도 함께 버린다.** DLAI 내부 프록시를 가리키므로
로컬에서 Claude 를 쓰려면 이 파일을 고쳐야 한다.

우리가 처음부터 로컬 키로 양쪽 provider 를 태워본 것이 결과적으로 맞았다.

### 정리

| 항목 | 우리 | 랩 | 판단 |
|---|---|---|---|
| 추상화 | 텍스트만 aisuite | provider SDK 직접 | 랩이 단순. 우리는 모듈 교체 이점 |
| OpenAI 이미지 | Chat Completions | Responses API | 둘 다 동작 |
| 블록 순서 | 텍스트 → 이미지 | 동일 | 일치 |
| 여러 텍스트 블록 | ❌ 첫 것만 | ✅ 전부 이어붙임 | **랩이 옳다** |
| Anthropic system | 없음 | 있으나 사용자 프롬프트와 충돌 | 우리가 낫다 |
| 태그 없는 응답 | 예외 | 복구 시도하나 오적용 | 우리가 낫다 |
| 스키마 | 손으로 쓴 블록 | 동일 (생성기는 미사용) | 일치 |
| 로더 검증 | `ValueError` | 없음 | 우리가 낫다 |

**고쳐야 할 것은 하나다** — 여러 텍스트 블록 처리. 나머지는 설계 차이거나 우리 쪽이 낫다.

## 9. 아직 열지 않은 것

없다. `utils.py` 까지 대조를 마쳤다.
