# labs — 강의 자료 원본

DeepLearning.AI [Agentic AI](https://www.deeplearning.ai/courses/agentic-ai) 랩 자료를 받은 그대로 보관하는 곳.

> ⚠ **코스 자료입니다.** 학습 참조용으로만 두며, 수정하지 않습니다.
> 저장소를 공개로 전환할 계획이 생기면 이 디렉터리를 먼저 검토해야 합니다.

## 보관 중인 자료

| 모듈 | 파일 | 내용 |
|---|---|---|
| 2 | [M2_UGL_1.html](module-2/M2_UGL_1.html) | Chart Generation 랩 노트북 HTML 내보내기 (340KB) |
| 2 | [coffee_sales.csv](module-2/coffee_sales.csv) | 데이터셋 3,636행 · 2024-03-01 ~ 2025-03-23 |
| 2 | [chart_v1.png](module-2/chart_v1.png) · [chart_v2.png](module-2/chart_v2.png) | 랩이 실제로 생성한 V1·V2 차트 |

`utils.py`는 아직 받지 않았습니다 — `image_openai_call`/`image_anthropic_call`이
[chart-agent](../projects/chart-agent/README.md) 3단계의 정답지라 그 단계를 마친 뒤 대조합니다.

## 원칙

1. **수정하지 않는다.** 원본 그대로 둔다 ([CLAUDE.md](../CLAUDE.md) 하드 제약 4번).
   고칠 것이 있으면 `projects/` 아래에 새 파일로 만든다.
2. 랩을 재현한 코드는 `projects/`에 둔다.
   현재 대응: [projects/chart-agent](../projects/chart-agent/README.md)
3. **부속 파일까지 함께 받는다.** 노트북만 받으면 `utils.py`·데이터·산출물이 빠져
   재현이 막힌다. 모듈 2에서 실제로 그랬고, CSV를 받기 전까지 데이터셋을 직접 생성했다.

## 무료 티어에서의 상황

랩 **실행 환경**은 Pro 전용이라 접근할 수 없습니다. 코드와 데이터는 파일 브라우저에서
받을 수 있어, [chart-agent](../projects/chart-agent/PLAN.md)가 이를 명세로 삼아
자체 구현합니다 — 실행만 우리 환경에서 합니다.
