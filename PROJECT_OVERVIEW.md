# 프로젝트 전체 이해 가이드

## 이 프로젝트가 뭔가요? (한 줄 요약)

> **"서버 장애가 나면, AI가 로그/메트릭/트레이스를 분석하고, 대응 매뉴얼(런북)까지 찾아서 장애 보고서를 자동으로 작성해주는 시스템"**

현실 비유: **병원 응급실**과 같다.

| 병원 응급실 | 이 프로젝트 |
|---|---|
| 환자(증상 데이터) | 장애 시나리오 (fixture 데이터) |
| 혈액검사 전문의 | **Log Agent** (로그 분석) |
| 영상의학 전문의 | **Metric Agent** (메트릭 분석) |
| 심전도 전문의 | **Trace Agent** (트레이스 분석) |
| 종합진단 + 처방전 작성 의사 | **Report Agent** (최종 보고서) |
| 의학 교과서/매뉴얼 | **런북(Runbook)** |

---

## 전체 흐름 (5단계)

```
1. 장애 시나리오 선택 (예: "DB 커넥션 실패")
       │
2. Prep 노드: 해당 시나리오의 가짜 데이터(fixture)를 읽어옴
       │
       ├──→ 3a. Log Agent: 로그만 보고 분석
       ├──→ 3b. Metric Agent: 메트릭만 보고 분석  (3개가 동시에 실행!)
       └──→ 3c. Trace Agent: 트레이스만 보고 분석
                    │
                    ▼ (3개 모두 완료되면)
4. Report Agent: 3개 분석 결과를 종합 + 런북 검색 → 최종 보고서 작성
       │
5. 출력: 장애 요약, 원인, 심각도, 즉시 조치, 후속 조치
```

---

## 폴더별 역할 (지도처럼 보기)

```
observability_agents_graph/
├── fixtures/          ← "가짜 환자 데이터" (테스트용 로그/메트릭/트레이스)
│   ├── normal/            정상 상태
│   ├── db_connection_failure/   DB 연결 장애
│   ├── traffic_spike/     트래픽 폭주
│   └── opensearch_index_delay/  검색 엔진 지연
│
├── agents/            ← "전문의들" (각각 하나의 데이터만 분석)
│   ├── log_agent.py       로그 분석 전문가
│   ├── metric_agent.py    메트릭 분석 전문가
│   ├── trace_agent.py     트레이스 분석 전문가
│   └── report_agent.py    종합 보고서 작성자
│
├── tools/             ← "도구들" (Agent가 사용하는 함수)
│   ├── mock_queries.py            fixture에서 데이터 읽기
│   ├── runbook_knowledge_base.py  런북을 벡터DB에 저장/검색
│   └── runbook_search.py          Agent가 호출하는 런북 검색 함수
│
├── runbooks/          ← "대응 매뉴얼" (장애별 조치 방법)
│   ├── db_connection_failure.md
│   ├── traffic_spike.md
│   └── ...
│
├── orchestrators/     ← "지휘자" (Agent들을 그래프로 연결)
│   └── incident_graph.py
│
├── schemas.py         ← "양식" (분석 결과/보고서의 구조 정의)
├── main_graph.py      ← "실행 버튼" (프로그램 시작점)
└── main.py            ← "실행 버튼" (그래프 없는 순차 실행 버전)
```

---

## 핵심 파일 6개, 하나씩 설명

### 1. `schemas.py` - "양식지"

AI가 아무렇게나 답하면 안 되니까, **답변 형식을 강제**하는 Pydantic 모델이다.

```python
Severity = Literal["info", "low", "medium", "high", "critical"]
Priority = Literal["low", "medium", "high"]
AnalysisType = Literal["log", "metric", "trace"]
```

- `AnalysisResult`: 개별 Agent의 분석 결과 양식 (요약, 근거, 의심 원인, 심각도 등)
- `IncidentReport`: 최종 보고서 양식 (장애 요약, 원인, 즉시 조치, 후속 조치 등)

### 2. `tools/mock_queries.py` - "가짜 데이터 읽기"

실제 운영 환경에서는 AWS OpenSearch나 Prometheus에서 데이터를 가져오겠지만, 여기서는 **JSON 파일에서 읽어오는 것으로 대체**한다.

```python
def query_logs(
    service: str,
    start_time: str,
    end_time: str,
    keywords: list[str] | None = None,
    limit: int = 50,
    scenario: str = "normal",
) -> dict[str, Any]:
    data = _load_json(FIXTURE_DIR / scenario / "logs.json")
```

`scenario`에 따라 `fixtures/db_connection_failure/logs.json` 같은 파일을 읽는다.

### 3. `agents/log_agent.py` - "로그 전문가"

Strands SDK의 `Agent`를 감싸는 클래스이다. 핵심은 이것:

```python
result = self.agent(
    prompt,
    structured_output_model=AnalysisResult,
)
return result.structured_output
```

- `self.agent(prompt, ...)`: LLM(AI)에게 프롬프트를 보냄
- `structured_output_model=AnalysisResult`: "이 양식에 맞춰서 답해"라고 강제
- `result.structured_output`: AI가 양식에 맞춰 답한 Python 객체를 반환

`metric_agent.py`, `trace_agent.py`도 구조가 같고, 각각 메트릭/트레이스만 분석한다.

### 4. `orchestrators/incident_graph.py` - "지휘자" (가장 핵심!)

**Agent들을 그래프(DAG)로 연결**하는 파일이다.

```python
def build_incident_graph() -> Any:
    # 1) Agent 4개 생성 (logs, metrics, traces, report)
    # 2) prep 노드 생성 (fixture 읽기)
    # 3) 그래프 연결:
    #    prep -> logs, metrics, traces (3개 동시 실행)
    #    logs, metrics, traces -> report (3개 다 끝나면 실행)

    builder.add_edge("prep", "logs")
    builder.add_edge("prep", "metrics")
    builder.add_edge("prep", "traces")

    and_condition = all_dependencies_complete(["logs", "metrics", "traces"])
    builder.add_edge("logs", "report", condition=and_condition)
    builder.add_edge("metrics", "report", condition=and_condition)
    builder.add_edge("traces", "report", condition=and_condition)
```

`FixturePrepNode`은 LLM 없이 단순히 JSON 파일을 읽어서 다음 노드들에 전달하는 역할이다.

### 5. `tools/runbook_knowledge_base.py` - "매뉴얼 검색 엔진"

런북 `.md` 파일들을 **벡터 DB(ChromaDB)에 저장**하고, 의미 기반 검색을 한다.

동작 순서:
1. 런북 파일을 `##` 기준으로 쪼갬 (청킹)
2. 각 조각을 벡터(숫자 배열)로 변환해서 ChromaDB에 저장
3. "DB 커넥션 실패"라고 검색하면, 의미가 비슷한 런북 조각을 찾아 반환

### 6. `main_graph.py` - "실행 버튼"

```python
def run(scenario: str):
    graph = build_incident_graph()
    task = {
        "scenario": scenario,
        "service": "payment-api",
        "start_time": "2026-03-01T14:00:00Z",
        "end_time": "2026-03-01T14:05:00Z",
    }
    result = graph(json.dumps(task, ensure_ascii=False))
```

시나리오를 선택해서 그래프를 실행하고, 결과를 예쁘게 출력한다.

---

## 추천 학습 순서

이미 `LEARNING_GUIDE.md`라는 학습 가이드가 프로젝트에 포함되어 있다. 아래 순서로 읽어보자:

1. **`fixtures/` 폴더의 JSON 파일 하나** 열어보기 - 어떤 데이터가 들어가는지 감 잡기
2. **`schemas.py`** 읽기 - 입출력 "양식"을 먼저 이해
3. **`tools/mock_queries.py`** 읽기 - fixture에서 데이터를 어떻게 읽는지
4. **`agents/log_agent.py`** 읽기 - Agent 하나가 어떻게 동작하는지 (나머지 Agent도 같은 구조)
5. **`orchestrators/incident_graph.py`** 읽기 - Agent들이 어떻게 연결되는지
6. **`tools/runbook_knowledge_base.py`** + **`LEARNING_GUIDE.md`** 함께 읽기 - RAG/벡터 검색 이해
7. **`main_graph.py`** 읽기 - 전체를 실행하는 진입점

이 순서는 **데이터 → 양식 → 도구 → 개별 Agent → 전체 연결 → 실행**의 흐름이라, 앞 단계를 이해하면 다음 단계가 자연스럽게 이해된다.

---

## 핵심 개념 요약

| 개념 | 설명 |
|---|---|
| **Strands SDK** | AWS가 만든 AI Agent 프레임워크. `Agent` 클래스로 LLM을 호출하고, `GraphBuilder`로 여러 Agent를 연결 |
| **Pydantic** | Python 데이터 검증 라이브러리. `BaseModel`을 상속해서 AI 출력 양식을 강제 |
| **RAG** | Retrieval-Augmented Generation. LLM이 답변 전에 관련 문서를 먼저 검색해서 참고하는 패턴 |
| **ChromaDB** | 벡터 데이터베이스. 텍스트를 숫자 벡터로 변환해서 "의미가 비슷한 문서"를 검색 |
| **청킹(Chunking)** | 긴 문서를 의미 단위(섹션)로 쪼개서 검색 정확도를 높이는 기법 |
| **Graph/DAG** | 방향성 비순환 그래프. Agent들의 실행 순서와 의존관계를 정의 |
| **Fixture** | 테스트용 가짜 데이터. 실제 서버 없이도 시스템을 시험할 수 있게 함 |
| **Observability** | 시스템의 내부 상태를 외부에서 관찰하는 것. 로그/메트릭/트레이스가 3대 축 |
