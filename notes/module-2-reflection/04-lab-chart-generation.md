# 04. Ungraded Lab: Chart Generation

> Module 2 · Lesson 4 (Code Example · 15m)
> 이전 ← [03. 차트 생성 워크플로우](03-chart-generation-workflow.md) · 다음 → [05. 리플렉션의 효과 평가하기](05-evaluating-reflection.md)

## 접근 불가

이 랩은 **Pro 전용**이라 무료 티어에서 열리지 않습니다.
[루트 README](../../README.md)에 기록한 대로, 이 코스의 ungraded 랩은 전부 잠겨 있습니다.

Notion 원본 노트에도 이 항목은 제목만 있고 내용이 없습니다.

## 랩 없이 무엇을 알 수 있나

[03번 노트](03-chart-generation-workflow.md)의 슬라이드가 이 랩이 무엇을 하는지 상당히 구체적으로 보여줍니다.

| 항목 | 내용 |
|---|---|
| 입력 | `coffee_sales.csv` — date, price, coffee_name |
| 과제 | 2024 vs 2025 Q1 커피 판매 비교 플롯 |
| v1 결과 | 누적 막대 그래프 (`plot.png`) — 음료별 비교 불가 |
| 검토 | v1 코드 + 이미지를 멀티모달 LLM에 입력 |
| v2 결과 | 분리 막대 그래프 (`plot_v2.png`) |
| 사용 라이브러리 | `matplotlib`, `pandas` |

즉 **재현에 필요한 정보는 거의 다 나와 있습니다.**

## 직접 만든다면

모듈 1에서 [리서치 에이전트를 자체 구현](../../projects/research-agent/README.md)했던 것과 같은 방식이 가능합니다. 필요한 조각:

1. 커피 판매 CSV 생성 (날짜·가격·음료명, 2024~2025)
2. 코드 생성 → 실행 → 이미지 저장
3. 이미지를 base64로 인코딩해 멀티모달 모델에 전달
4. 비평 → 코드 수정 → 재실행
5. [05번 노트](05-evaluating-reflection.md)의 **루브릭 채점**으로 v1 vs v2 비교

3번이 모듈 1에서 하지 않은 유일하게 새로운 부분입니다.
리서치 에이전트의 검토는 텍스트만 다뤘습니다.

📌 현재 이 저장소에는 구현하지 않았습니다. 진행 여부는 미정입니다.
