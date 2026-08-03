# 작업 체크리스트

> 기획서: [PLAN.md](PLAN.md) · 최종 수정 2026-08-03

## 진행 상황

| 단계 | 상태 |
|---|---|
| 0. 준비 | ✅ 완료 |
| 1. 도구 계층 | ✅ 완료 (검증 통과) |
| 2. LLM 계층 | ✅ 완료 (실호출 검증) |
| 3. 에이전트 + 워크플로우 | ✅ 완료 (실행 성공) |
| 4. 평가 | ✅ 완료 (8/8 통과) |
| 5. 실행·검증 | ✅ 완료 |
| 6. 회고 | ✅ 완료 |

---

## 0. 준비

- [x] 기획서 작성 (`PLAN.md`)
- [x] 작업 체크리스트 작성 (이 문서)
- [x] 루트에 `.env` / `.env.example` / `.gitignore` 생성
- [x] `TAVILY_API_KEY` 설정 — 실호출 검증 완료
- [x] `OPENAI_API_KEY` 설정 — aisuite 경유 실호출 검증 완료

## 1. 도구 계층

- [x] `config.py` — 모델명, 상수, API 키 검증
- [x] `tools.py` — docstring→JSON Schema 변환, 레지스트리
- [x] `search_web` (Tavily) — 키 없으면 자동 제외되는 조건부 등록, 실호출 검증 완료
- [x] **`wikipedia` 패키지 동작 검증** — 정상 동작 (bs4 4.15.0과 충돌 없음)
- [x] `search_arxiv` 실제 호출 검증 — Atom XML 파싱 정상
- [x] 생성된 스키마 육안 확인 — docstring의 설명·타입·required가 의도대로 반영됨

**검증 명령**
```bash
./venv/bin/python -c "
from research_agent.tools import TOOL_SCHEMAS, search_wikipedia, search_arxiv
import json; print(json.dumps(TOOL_SCHEMAS, indent=2, ensure_ascii=False))
print(search_wikipedia('agentic AI', 1))
print(search_arxiv('reflection agent LLM', 2))
"
```

## 2. LLM 계층

- [x] `llm.py` — aisuite 클라이언트 래퍼 (`complete()`)
- [x] `llm.py` — **도구 호출 루프 직접 구현** ← 학습 핵심
  - [x] 스키마 전달 (`max_turns` 없이 → 자동 실행 회피)
  - [x] `tool_calls` 파싱
  - [x] assistant 메시지 재구성 후 messages에 추가
  - [x] 도구 실행 → `role: "tool"` 메시지로 되먹임
  - [x] `MAX_TOOL_TURNS` 상한 도달 시 도구 없이 강제 답변
  - [x] 알 수 없는 도구명·인자 파싱 실패를 모델에게 에러로 반환 (조용한 무시 없음)
  - [x] **실제 호출 검증** — 2턴, `search_web` 1회, URL 2개 정상 수집
- [x] `trace.py` — 단계별 기록, `collected_urls()` (인용 정합성 eval의 근거), JSON 저장
- [x] `trace.py` 저장 동작 검증 — `traces/*.json` 2건 생성 확인

## 3. 에이전트 + 워크플로우

- [x] `agents.py` — 7개 함수
  - [x] `plan_research()` — 리서치 질문 목록 수립
  - [x] `gather_sources()` — **도구 호출하는 유일한 단계**
  - [x] `synthesize()` — 종합·순위화·중복 제거
  - [x] `write_outline()`
  - [x] `write_draft()`
  - [x] `critique()` — 반성: 무엇을 고쳐야 하는가
  - [x] `revise()` — 최종 마크다운 리포트
- [x] `workflow.py` — 7단계 파이프라인 조립 + 트레이스 연결
- [x] `run.py` — CLI (`python run.py "주제" [--model] [--out]`)
- [x] 각 프롬프트에 인라인 인용 + References 요구사항 명시

## 4. 평가

- [x] `evals.py`
  - [x] **인용 정합성** — 리포트 URL ⊆ 수집 소스 URL ← 대표 지표
  - [x] References 섹션 존재
  - [x] 링크 HTTP 200 비율
  - [x] 소스 도메인 다양성
  - [x] 단어 수 ≥ 400
  - [x] `textstat` 가독성 점수
  - [x] 도구 호출 0건이면 실패 처리
- [x] eval 결과를 JSON + 표로 출력

## 5. 실행·검증

- [x] 전체 실행 2회 (강의 데모 주제, 각 약 2분)
- [x] **초안 vs 최종본 diff** — 18.6% 변경. 반성이 실제로 일함 (eval로 자동 판정)
- [x] eval 실행 → **8/8 통과**. 1차 6/8 → 원인 분리 후 수정 → 8/8
- [x] 트레이스 육안 검토 — 데이터 흐름 매트릭스로 확인. 모든 단계가 앞 단계 출력을 100% 수신
- [x] 완료 기준 5개 충족 확인 — 전부 충족 ([PLAN.md §2](PLAN.md)에 결과 기록)
- [x] `README.md` 작성 — mermaid 다이어그램 5개, 사용법, 실제 출력, 개선 기록

## 6. 회고 — 완성 후에만

- [x] eval 결과 기반 문제점 정리 — 링크 평가 오측정, 가독성 실결함 (README에 기록)
- [x] 트레이스 기반 오류 분석 — 데이터 흐름 매트릭스, 2단계 정보 압축·프롬프트 누적 관찰
- [x] **공식 저장소와 대조** — 1,107줄 전체 검토, 라우팅 결함 재현 확인
- [x] 대조 회고를 `notes/`에 기록 — [research-agent-vs-official.md](../../notes/retrospectives/research-agent-vs-official.md)

---

## 규칙

1. **6번 전까지 공식 저장소 코드를 열지 않는다.** 정답을 보면 학습 가치가 사라진다.
2. 단계를 건너뛰지 않는다. 특히 1번의 `wikipedia` 검증 — 여기서 막히면 뒤가 전부 막힌다.
3. 프레임워크(LangChain/CrewAI 등)를 도입하지 않는다.
4. 각 단계 완료 시 이 문서의 체크박스를 갱신한다.
