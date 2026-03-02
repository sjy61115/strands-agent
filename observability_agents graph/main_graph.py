import json

from orchestrators.incident_graph import build_incident_graph


def pretty_print(title: str, obj):
    # pydantic v2/v1 안전 출력
    if hasattr(obj, "model_dump"):
        payload = obj.model_dump()
    elif hasattr(obj, "dict"):
        payload = obj.dict()
    else:
        payload = obj
    print(f"\n=== {title} ===")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def run(scenario: str):
    graph = build_incident_graph()

    # 중요: 원래 task에는 raw 데이터를 넣지 않는다.
    # raw는 prep 노드가 fixture에서 읽어 downstream으로만 흘려보냄.
    task = {
        "scenario": scenario,
        "service": "payment-api",
        "start_time": "2026-03-01T14:00:00Z",
        "end_time": "2026-03-01T14:05:00Z",
    }

    result = graph(json.dumps(task, ensure_ascii=False))

    # GraphResult.results[node_id] = NodeResult 
    logs_ar = result.results["logs"].get_agent_results()[0]
    metrics_ar = result.results["metrics"].get_agent_results()[0]
    traces_ar = result.results["traces"].get_agent_results()[0]
    report_ar = result.results["report"].get_agent_results()[0]

    pretty_print("LOG ANALYSIS", logs_ar.structured_output)
    pretty_print("METRIC ANALYSIS", metrics_ar.structured_output)
    pretty_print("TRACE ANALYSIS", traces_ar.structured_output)
    pretty_print("FINAL INCIDENT REPORT", report_ar.structured_output)


if __name__ == "__main__":
    run("db_connection_failure")  # normal / db_connection_failure / traffic_spike / opensearch_index_delay
