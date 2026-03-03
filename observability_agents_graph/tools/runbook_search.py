import json
from typing import Any

from tools.runbook_knowledge_base import RunbookKnowledgeBase

_kb: RunbookKnowledgeBase | None = None


def _get_kb() -> RunbookKnowledgeBase:
    global _kb
    if _kb is None:
        _kb = RunbookKnowledgeBase()
    return _kb


def search_runbooks(query: str, n_results: int = 5) -> str:
    """
    장애 상황에 맞는 런북(운영 대응 절차)을 Knowledge Base에서 검색한다.

    Args:
        query: 검색할 장애 상황 설명 (예: "database connection pool exhausted")
        n_results: 반환할 결과 수 (기본 5)

    Returns:
        관련 런북 조각들이 담긴 JSON 문자열
    """
    kb = _get_kb()
    results = kb.search(query, n_results=n_results)
    output: dict[str, Any] = {
        "source": "runbook_knowledge_base",
        "query": query,
        "total_results": len(results),
        "results": results,
    }
    return json.dumps(output, ensure_ascii=False, indent=2)
