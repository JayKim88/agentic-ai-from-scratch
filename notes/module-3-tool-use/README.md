# Module 3 — 도구 사용 (Tool Use)

DeepLearning.AI [Agentic AI](https://www.deeplearning.ai/courses/agentic-ai) 모듈 3 학습 정리.
원본 노트: [Notion — Module 3: Tool use](https://app.notion.com/p/3b4e5ccd65b18033addec6c84d9f03b3)

## 목차

| # | 레슨 | 핵심 내용 |
|---|---|---|
| 01 | [도구란 무엇인가](01-what-are-tools.md) | **LLM이 호출 여부를 스스로 결정**, 점선 박스 표기, 캘린더 비서 |
| 02 | [도구 만들기](02-creating-a-tool.md) | LLM은 실행하지 않는다 — `FUNCTION:` 마커, **현대 `tool_calls` 응답 구조(실측)** |
| 03 | [도구 문법](03-tool-syntax.md) | **docstring → JSON Schema 자동 변환.** `max_turns` |
| 04 | [Ungraded Lab: 함수를 도구로](04-lab-functions-into-tools.md) | 📌 랩 자료 받으면 작성 |
| 05 | [Ungraded Lab: 이메일 어시스턴트](05-lab-email-assistant.md) | 📌 랩 자료 받으면 작성 |
| 06 | [코드 실행](06-code-execution.md) | 도구 개수 폭발의 해법, **샌드박스**, 리플렉션 얹기 |
| 07 | [MCP](07-mcp.md) | **M × N → M + N**, 클라이언트/서버, 다음 모듈 예고 |

> ⚠ 원본 노션 노트의 **"Tool syntax" 절에는 앞 레슨의 요약이 그대로 복사**돼 있습니다.
> 03번 노트는 슬라이드 두 장을 직접 읽어 작성했습니다.

## 모듈 3을 한 장으로

**1. 도구 사용이란**
LLM이 **함수를 호출할지 스스로 결정**하게 하는 것. 모듈 1·2의 하드코딩 워크플로우와
갈라지는 지점이 여기다.

**2. LLM은 함수를 실행하지 않는다**
토큰을 생성할 뿐이다. **"불러달라"는 신호를 텍스트로 내고**, 실행과 되먹임은 개발자 코드가 한다.
예전엔 `FUNCTION: get_current_time()` 같은 마커를 정규식으로 잡았다.
현대 API 는 `finish_reason="tool_calls"` 와 별도 필드로 분리해서 준다 —
`content` 는 아예 `None` 이다.

**3. 현대 방식 — 함수를 그냥 넘긴다**
```python
tools=[get_current_time]      # 함수 객체를 그대로
```
JSON Schema가 자동 생성된다.

| Schema | 출처 |
|---|---|
| `name` | 함수 이름 |
| `description` | **docstring** |
| `parameters` | 시그니처 + docstring |

**docstring이 곧 모델이 읽는 인터페이스다.** 부실하게 쓰면 인자를 엉뚱하게 채운다.

**4. 도구를 무한히 만들지 말고 코드를 실행시켜라**
계산기 버튼 수만큼 도구를 만드는 대신 LLM에게 코드를 쓰게 하면 거의 다 덮인다.
실패하면 **오류를 되먹여** 고치게 한다 — 모듈 2의 외부 피드백이 여기서 다시 나온다.

**5. 그 대가는 위험이다**
자율적인 코딩 도구가 프로젝트의 `.py` 파일을 전부 지운 실제 사례가 있다.
**모범 사례는 샌드박스** (Docker, E2B).

**6. MCP — 연동을 표준화한다**
앱 M개 × 도구 N개마다 래퍼를 만들던 것을 **M + N**으로 줄인다.
**클라이언트**(도구를 쓰는 앱) / **서버**(데이터·서비스 래퍼), 서버 하나가 도구 여러 개를 준다.

**7. 다음 모듈이 가장 중요할 수 있다**
> 팀을 가르는 가장 큰 차이는 **체계적인 평가 프로세스**를 운영할 수 있는 능력이다.

---

## 이 저장소의 앞선 작업과 이어지는 지점

| 모듈 3 개념 | 이미 해본 것 |
|---|---|
| `FUNCTION:` 마커 → 정규식 추출 | [chart-agent](../../projects/chart-agent/README.md)의 `<execute_python>` 태그 |
| 코드 실행 + 격리 | chart-agent의 `python -I` 서브프로세스 · 타임아웃 |
| 코드 실행 + 오류 되먹임 | 모듈 2 [06번](../module-2-reflection/06-using-external-feedback.md) 외부 피드백 |
| 실행 결과를 검토에 넣기 | [sql-agent](../../projects/sql-agent/README.md) — 0/5 → 10/10 |
| 위험한 동작 차단 | sql-agent의 읽기 전용 연결 (`DROP` 차단) |
| docstring → 스키마 | `requirements.txt`의 `docstring-parser` |

**모듈 2의 랩들은 도구 호출을 예전 방식으로 손수 구현한 셈**이었습니다.
모듈 3은 그것을 표준 문법으로 대체합니다.

## 랩 자료

랩 2개는 아직 자료를 받지 않았습니다. 받으면 [`labs/module-3/`](../../labs/README.md)에
보관하고 04·05번 노트를 채웁니다.
