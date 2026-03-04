"""
test_runbook_search.py

search_runbooks 도구와 RunbookKnowledgeBase의 동작을 검증한다.
- @tool 데코레이터가 적용되어 있는지
- 각 시나리오 쿼리에 대해 관련 런북이 반환되는지
- 반환된 결과 구조가 올바른지
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.runbook_search import search_runbooks
from tools.runbook_knowledge_base import RunbookKnowledgeBase


# ── @tool 데코레이터 적용 여부 ────────────────────────────────────────────────

def test_search_runbooks_is_strands_tool():
    """search_runbooks에 @tool 데코레이터가 적용되어 tool_spec이 존재하는지 검증."""
    assert hasattr(search_runbooks, "tool_spec"), (
        "search_runbooks에 @tool 데코레이터가 없음. "
        "from strands import tool 후 @tool을 추가해야 함."
    )


# ── RunbookKnowledgeBase 직접 검색 테스트 ─────────────────────────────────────

def test_kb_indexes_runbook_files():
    """RunbookKnowledgeBase가 runbooks/*.md 파일을 인덱싱하는지 검증."""
    kb = RunbookKnowledgeBase()
    count = kb._collection.count()
    assert count > 0, "런북 파일이 하나도 인덱싱되지 않음"


def test_kb_search_returns_results_for_db_failure():
    """DB 커넥션 장애 쿼리에서 db_connection_failure.md 런북이 반환되는지 검증."""
    kb = RunbookKnowledgeBase()
    results = kb.search("database connection pool exhausted connection refused", n_results=5)

    assert len(results) > 0, "DB 장애 쿼리 결과가 비어있음"

    sources = [r["source"] for r in results]
    assert any("db_connection_failure" in s for s in sources), (
        f"db_connection_failure.md가 결과에 없음. 반환된 source 목록: {sources}"
    )


def test_kb_search_returns_results_for_traffic_spike():
    """트래픽 급증 쿼리에서 traffic_spike.md 런북이 반환되는지 검증."""
    kb = RunbookKnowledgeBase()
    results = kb.search("traffic spike high request rate service overload rate limiting", n_results=5)

    assert len(results) > 0, "트래픽 급증 쿼리 결과가 비어있음"

    sources = [r["source"] for r in results]
    assert any("traffic_spike" in s for s in sources), (
        f"traffic_spike.md가 결과에 없음. 반환된 source 목록: {sources}"
    )


def test_kb_search_returns_results_for_opensearch_delay():
    """OpenSearch 인덱싱 지연 쿼리에서 opensearch_index_delay.md 런북이 반환되는지 검증."""
    kb = RunbookKnowledgeBase()
    results = kb.search("opensearch indexing delay ingestion backlog", n_results=5)

    assert len(results) > 0, "OpenSearch 지연 쿼리 결과가 비어있음"

    sources = [r["source"] for r in results]
    assert any("opensearch_index_delay" in s for s in sources), (
        f"opensearch_index_delay.md가 결과에 없음. 반환된 source 목록: {sources}"
    )


def test_kb_search_result_structure():
    """검색 결과의 필드 구조가 올바른지 검증."""
    kb = RunbookKnowledgeBase()
    results = kb.search("database connection", n_results=1)

    assert len(results) == 1
    result = results[0]

    assert "source" in result
    assert "section" in result
    assert "content" in result
    assert "relevance_score" in result
    assert 0.0 <= result["relevance_score"] <= 1.0


# ── search_runbooks 도구 함수 통합 테스트 ─────────────────────────────────────

def test_search_runbooks_returns_json_string():
    """search_runbooks가 JSON 문자열을 반환하는지 검증."""
    raw = search_runbooks("database connection pool exhausted")
    assert isinstance(raw, str), "search_runbooks의 반환값이 str이 아님"

    parsed = json.loads(raw)
    assert "results" in parsed
    assert "total_results" in parsed
    assert parsed["total_results"] > 0


def test_search_runbooks_db_failure_finds_runbook():
    """DB 장애 쿼리 시 runbook_references에 사용할 source 정보가 포함되는지 검증."""
    raw = search_runbooks("database connection pool exhausted connection refused", n_results=5)
    parsed = json.loads(raw)

    sources = [r["source"] for r in parsed["results"]]
    assert any("db_connection_failure" in s for s in sources), (
        f"db_connection_failure.md가 결과에 없음. sources={sources}"
    )


def test_search_runbooks_n_results_respected():
    """n_results 파라미터가 반환 개수를 제한하는지 검증."""
    raw = search_runbooks("payment api incident", n_results=2)
    parsed = json.loads(raw)

    assert len(parsed["results"]) <= 2
