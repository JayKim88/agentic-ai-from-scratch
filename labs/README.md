# labs — 강의 자료 원본

DeepLearning.AI [Agentic AI](https://www.deeplearning.ai/courses/agentic-ai) 랩 자료를 받은 그대로 보관하는 곳.

> ⚠ **코스 자료입니다.** 학습 참조용으로만 두며, 수정하지 않습니다.
> 저장소를 공개로 전환할 계획이 생기면 이 디렉터리를 먼저 검토해야 합니다.

## 보관 중인 자료

| 모듈 | 파일 | 내용 |
|---|---|---|
| 2 | [module-2/M2_UGL_1.html](module-2/M2_UGL_1.html) | Chart Generation 랩 노트북 HTML 내보내기 (340KB) |

## 원칙

1. **수정하지 않는다.** 원본 그대로 둔다 ([CLAUDE.md](../CLAUDE.md) 하드 제약 4번).
   고칠 것이 있으면 `projects/` 아래에 새 파일로 만든다.
2. 랩을 재현한 코드는 `projects/`에 둔다.
   현재 대응: [projects/chart-agent](../projects/chart-agent/README.md)
3. 부속 파일(`utils.py`, 데이터 CSV)은 **함께 받아야** 한다.
   위 HTML은 노트북 본문만 있고 부속 파일이 없어, 재현 시 직접 만들어야 한다.

## 무료 티어에서의 상황

모든 랩(ungraded 포함)이 **Pro 전용**이라 실행 환경에는 접근할 수 없습니다.
`M2_UGL_1.html`은 노트북을 브라우저에서 내보낸 것이라 **코드와 출력은 읽을 수 있지만
실행은 불가능**합니다. 그래서 [chart-agent](../projects/chart-agent/PLAN.md)가
이 HTML을 명세로 삼아 자체 구현합니다.
