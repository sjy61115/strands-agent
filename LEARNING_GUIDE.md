# Run-Book Knowledge Base 학습 가이드

## 1. Run-Book이란?

런북은 **"장애가 나면 이렇게 대응하라"는 운영 매뉴얼**이다. 소방서의 화재 대응 매뉴얼과 같다.

예를 들어 `traffic_spike.md`를 보면:

```markdown
# Run-Book: Traffic Spike / 과부하

## 증상
- RateLimiter에서 request volume 급증 경고
- ApiGateway upstream response latency 증가
- HTTP 503 Service Unavailable 에러 발생
```

"이런 증상이 보이면 → 이런 순서로 조치하라"가 정리되어 있다.
보통 실제 운영팀에서는 Confluence, Notion, 또는 S3에 이런 문서를 쌓아둔다.

**문제는**: 런북이 100개, 1000개가 되면 "지금 이 장애에 어떤 런북이 관련 있지?"를 사람이 찾기 어렵다.
여기서 AI + 벡터 검색이 등장한다.

---

## 2. RAG (Retrieval-Augmented Generation) 패턴

이 프로젝트의 런북 시스템은 **RAG 패턴**을 구현한 것이다. 한 문장으로 정리하면:

> **LLM이 답변하기 전에, 관련 문서를 먼저 검색(Retrieval)해서 그 내용을 참고하여(Augmented) 답변을 생성(Generation)하는 것**

LLM은 학습 데이터에 없는 내용(회사 내부 런북 등)을 모른다. 그래서:

```
① 질문이 들어옴: "DB 커넥션이 끊겼어"
② 검색(R): 벡터DB에서 관련 런북 조각들을 찾음
③ 보강(A): 찾은 런북 내용을 LLM 프롬프트에 붙여줌
④ 생성(G): LLM이 런북 내용을 참고해서 정확한 조치사항을 생성
```

이 프로젝트에서는 Report Agent가 `search_runbooks` tool을 호출하는 것이 R 단계이고,
그 결과를 보고 보고서를 쓰는 것이 A+G 단계이다.

---

## 3. 임베딩(Embedding)이란?

RAG의 핵심은 **"의미가 비슷한 문서를 찾는 것"**이다.
일반 텍스트 검색(ctrl+F)은 정확한 단어만 찾지만, 임베딩 검색은 **의미**로 찾는다.

```
텍스트                        →  임베딩 모델  →  숫자 벡터
"DB 커넥션 타임아웃"           →              →  [0.12, -0.45, 0.78, ...]
"database connection timeout"  →              →  [0.11, -0.43, 0.80, ...]  ← 비슷한 벡터!
"트래픽 급증으로 503 에러"      →              →  [0.89, 0.23, -0.15, ...]  ← 다른 벡터
```

같은 의미의 텍스트는 비슷한 숫자 배열(벡터)이 된다.
이 벡터끼리의 거리를 비교하면 "의미적 유사도"를 계산할 수 있다.

ChromaDB는 기본으로 `all-MiniLM-L6-v2`라는 임베딩 모델을 내장하고 있어서,
별도로 임베딩 모델을 설정하지 않아도 자동으로 동작한다.
(처음 실행 시 약 80MB 모델을 다운로드한 것이 바로 이것이다.)

---

## 4. 벡터 데이터베이스 (Vector DB)

임베딩된 벡터들을 저장하고, "이 벡터와 가장 가까운 벡터 N개를 찾아줘"를
빠르게 수행하는 특수 DB이다.

### 아키텍처 이미지에서의 대응

| AWS 프로덕션 | 로컬 구현 | 역할 |
|---|---|---|
| S3 Bucket (Run-Book) | `runbooks/*.md` 파일 | 원본 문서 저장소 |
| OpenSearch Serverless | ChromaDB | 벡터 DB (임베딩 저장 + 유사도 검색) |
| Bedrock Knowledge Base | `RunbookKnowledgeBase` 클래스 | 청킹 + 인덱싱 + 검색 통합 |

### 코드에서의 설정

```python
# tools/runbook_knowledge_base.py
self._collection = self._client.get_or_create_collection(
    name="runbooks",
    metadata={"hnsw:space": "cosine"},
)
```

`"hnsw:space": "cosine"`은 벡터 간 거리를 **코사인 유사도**로 측정하겠다는 뜻이다.
코사인 유사도는 두 벡터의 방향이 얼마나 같은지를 0~1로 나타낸다.
(1이면 완전 동일 방향 = 완전 동일 의미)

---

## 5. 청킹(Chunking) - 문서를 왜 쪼개는가?

런북 하나가 통째로 벡터 하나가 되면 문제가 있다:

- 임베딩 모델에 입력 길이 제한이 있음 (보통 256~512 토큰)
- 문서 전체의 의미가 하나의 벡터로 뭉개져서 검색 정확도가 떨어짐

그래서 문서를 **의미 단위로 쪼개는 것**이 청킹이다.

### 이 프로젝트의 청킹 전략

마크다운의 `##` (h2 헤더)를 기준으로 분할한다.

`traffic_spike.md` 하나가 이렇게 분할된다:

```
청크 0: "# Run-Book: Traffic Spike..."     (overview)
청크 1: "## 증상\n- RateLimiter에서..."      (증상)
청크 2: "## 영향 범위\n- 서비스 응답..."      (영향 범위)
청크 3: "## 즉시 조치\n1. Auto-Scaling..."   (즉시 조치)
청크 4: "## 후속 조치\n1. Auto-Scaling..."   (후속 조치)
청크 5: "## 에스컬레이션\n- 스케일아웃..."    (에스컬레이션)
```

각 청크가 **개별 벡터**로 저장되므로,
"503 에러가 나고 있어"라고 검색하면 "증상" 섹션이 가장 높은 점수로 나온다.

### 코드 (tools/runbook_knowledge_base.py)

```python
def _chunk_by_section(self, content: str) -> list[dict]:
    """마크다운을 ## 섹션 기준으로 분할하여 청킹"""
    for line in content.split("\n"):
        if line.startswith("# ") and not title:
            title = line.lstrip("# ").strip()
        elif line.startswith("## "):
            # 이전 섹션을 저장하고 새 섹션 시작
            chunks.append({...})
            current_section = line.lstrip("# ").strip()
    return chunks
```

---

## 6. 검색 흐름 전체 정리

실제 테스트 결과로 흐름을 따라가 보면:

```
입력: "database connection pool exhausted timeout"
                    │
                    ▼
          ┌─ 임베딩 모델 ─┐
          │ [0.12, -0.45, │
          │  0.78, ...]   │
          └───────────────┘
                    │
                    ▼
          ┌─ ChromaDB 코사인 유사도 비교 ─┐
          │                               │
          │  db_connection_failure 증상    │ → 거리 0.3881 → 점수 0.6119 ✓ 가장 유사
          │  db_connection_failure 제목    │ → 거리 0.4652 → 점수 0.5348
          │  traffic_spike 증상           │ → 거리 0.7200 → 점수 0.2800 ✗ 관련 낮음
          └───────────────────────────────┘
```

점수 계산은 `1 - 거리`이다:

```python
# tools/runbook_knowledge_base.py
"relevance_score": round(1 - dist, 4)
```

- 거리가 0에 가까울수록 → 점수가 1에 가까움 → 의미가 유사
- 거리가 1에 가까울수록 → 점수가 0에 가까움 → 의미가 다름

---

## 7. Agent Tool로서의 통합

Strands Agent에서 **tool**은 "Agent가 스스로 판단해서 호출할 수 있는 함수"이다.

### Report Agent 설정 (orchestrators/incident_graph.py)

```python
report_agent = Agent(
    name="report_agent",
    system_prompt=(
        "너는 Report Generator이다.\n"
        "...\n"
        "반드시 search_runbooks 도구를 호출하여 해당 장애 유형에 맞는 런북을 검색하라.\n"
        "런북에서 찾은 즉시 조치와 후속 조치를 immediate_actions, follow_up_actions에 반영하라.\n"
    ),
    tools=[search_runbooks],           # ← Agent가 사용할 수 있는 도구 등록
    structured_output_model=IncidentReport,  # ← 출력 스키마
)
```

핵심 두 가지:
- **`tools=[search_runbooks]`**: Agent가 사용할 수 있는 도구 목록에 런북 검색을 등록
- **system_prompt**: "반드시 search_runbooks 도구를 호출하라"고 지시

Agent는 LLM이므로, 분석 결과를 읽고:
1. "이건 DB 커넥션 문제 같다" (판단)
2. `search_runbooks("database connection failure")` (tool 호출)
3. 런북 내용을 받아서 (검색 결과 수신)
4. 보고서에 반영 (생성)

이 과정을 **자율적으로** 수행한다.

---

## 8. 전체 아키텍처에서의 위치

```
                    ┌──────────────────────────────────┐
                    │     Orchestrator Agent (Graph)     │
                    │                                    │
  fixture 데이터 ──→ prep ──→ ┌─ logs_agent   ─┐       │
                              ├─ metrics_agent ─┤──→ report_agent ──→ IncidentReport
                              └─ traces_agent  ─┘       │     │
                    │                                    │     │
                    │         ┌───────────────────┐      │     │ search_runbooks()
                    │         │  Knowledge Base    │◀─────│─────┘
                    │         │  (ChromaDB)        │      │
                    │         │  ┌──────────────┐  │      │
                    │         │  │ runbooks/*.md │  │      │
                    │         │  │ → 청킹 → 임베딩 │  │      │
                    │         │  └──────────────┘  │      │
                    │         └───────────────────┘      │
                    └──────────────────────────────────┘
```

아키텍처 이미지에서 보면:
- **S3 Bucket Run-Book** = `runbooks/` 디렉토리
- **OpenSearch Serverless (Vector DB)** = ChromaDB
- **Knowledge Base** = `RunbookKnowledgeBase` 클래스
- **Bedrock가 LLM을 invoke** = Report Agent가 LLM으로 답변 생성

---

## 9. 프로젝트 파일 구조

```
observability_agents_graph/
├── runbooks/                              ← 런북 원본 문서 (S3 대체)
│   ├── db_connection_failure.md
│   ├── traffic_spike.md
│   ├── opensearch_index_delay.md
│   └── general_troubleshooting.md
├── tools/
│   ├── mock_queries.py                    ← 기존: fixture 기반 로그/메트릭/트레이스 조회
│   ├── runbook_knowledge_base.py          ← 벡터DB 래퍼 (ChromaDB)
│   └── runbook_search.py                  ← Agent tool 함수
├── orchestrators/
│   └── incident_graph.py                  ← 그래프 정의 (Report Agent에 tool 등록)
├── schemas.py                             ← RunbookReference, IncidentReport 스키마
└── main_graph.py                          ← 실행 진입점
```

---

## 10. 핵심 용어 정리

| 용어 | 의미 | 프로젝트에서의 역할 |
|---|---|---|
| **Run-Book** | 장애 대응 매뉴얼 | `runbooks/*.md` 파일들 |
| **RAG** | 검색 + LLM 생성 패턴 | Report Agent가 런북 검색 후 보고서 작성 |
| **Embedding** | 텍스트를 숫자 벡터로 변환 | ChromaDB 내장 `all-MiniLM-L6-v2` 모델 |
| **Vector DB** | 벡터 저장/유사도 검색 DB | ChromaDB (인메모리) |
| **Chunking** | 문서를 의미 단위로 분할 | `_chunk_by_section()` (`##` 기준) |
| **Cosine Similarity** | 벡터 간 방향 유사도 (0~1) | `hnsw:space: cosine` 설정 |
| **Knowledge Base** | 청킹+인덱싱+검색 통합 시스템 | `RunbookKnowledgeBase` 클래스 |
| **Tool (Agent)** | Agent가 자율 호출하는 함수 | `search_runbooks()` |
| **HNSW** | 벡터 근사 최근접 이웃 검색 알고리즘 | ChromaDB 내부 인덱스 구조 |
