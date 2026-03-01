import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
FIXTURE_DIR = BASE_DIR / "fixtures"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def query_logs(
    service: str,
    start_time: str,
    end_time: str,
    keywords: list[str] | None = None,
    limit: int = 50,
    scenario: str = "normal",
) -> dict[str, Any]:
    """
    로컬 fixture 기반 로그 조회.
    나중에 OpenSearch/Athena 구현으로 내부만 교체하면 됨.
    """
    data = _load_json(FIXTURE_DIR / scenario / "logs.json")
    items = [
        item for item in data.get("items", [])
        if item.get("service") == service
    ]

    if keywords:
        lowered = [k.lower() for k in keywords]
        items = [
            item for item in items
            if any(k in item.get("message", "").lower() for k in lowered)
        ]

    return {
        "source": "fixture_logs",
        "service": service,
        "start_time": start_time,
        "end_time": end_time,
        "scenario": scenario,
        "items": items[:limit],
        "total": len(items),
    }


def query_metrics(
    service: str,
    start_time: str,
    end_time: str,
    metric_name: str | None = None,
    promql: str | None = None,
    scenario: str = "normal",
) -> dict[str, Any]:
    data = _load_json(FIXTURE_DIR / scenario / "metrics.json")
    return {
        "source": "fixture_metrics",
        "service": service,
        "start_time": start_time,
        "end_time": end_time,
        "scenario": scenario,
        "metric_name": metric_name,
        "promql": promql,
        "items": data.get("items", []),
    }


def query_traces(
    service: str,
    start_time: str,
    end_time: str,
    error_only: bool = True,
    limit: int = 20,
    scenario: str = "normal",
) -> dict[str, Any]:
    data = _load_json(FIXTURE_DIR / scenario / "traces.json")
    items = [
        item for item in data.get("items", [])
        if item.get("service") == service
    ]

    if error_only:
        items = [item for item in items if item.get("status") == "ERROR"]

    return {
        "source": "fixture_traces",
        "service": service,
        "start_time": start_time,
        "end_time": end_time,
        "scenario": scenario,
        "items": items[:limit],
        "total": len(items),
    }
