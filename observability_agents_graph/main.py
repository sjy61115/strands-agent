import json

from agents import LogAnalysisAgent, MetricAnalysisAgent, TraceAnalysisAgent, ReportAgent
from tools.mock_queries import query_logs, query_metrics, query_traces


def pretty_print_model(title: str, model_obj):
    if hasattr(model_obj, "model_dump"):
        payload = model_obj.model_dump()
    else:
        payload = model_obj.dict()

    print(f"\n=== {title} ===")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def run_scenario(
    scenario: str,
    service: str = "payment-api",
    start_time: str = "2026-03-01T14:00:00Z",
    end_time: str = "2026-03-01T14:05:00Z",
):
    log_data = query_logs(
        service=service,
        start_time=start_time,
        end_time=end_time,
        scenario=scenario,
    )
    metric_data = query_metrics(
        service=service,
        start_time=start_time,
        end_time=end_time,
        scenario=scenario,
    )
    trace_data = query_traces(
        service=service,
        start_time=start_time,
        end_time=end_time,
        scenario=scenario,
    )

    log_agent = LogAnalysisAgent()
    metric_agent = MetricAnalysisAgent()
    trace_agent = TraceAnalysisAgent()
    report_agent = ReportAgent()

    log_result = log_agent.analyze(log_data, service, start_time, end_time)
    metric_result = metric_agent.analyze(metric_data, service, start_time, end_time)
    trace_result = trace_agent.analyze(trace_data, service, start_time, end_time)

    report_result = report_agent.build_report(
        log_analysis=log_result,
        metric_analysis=metric_result,
        trace_analysis=trace_result,
    )

    pretty_print_model("LOG ANALYSIS", log_result)
    pretty_print_model("METRIC ANALYSIS", metric_result)
    pretty_print_model("TRACE ANALYSIS", trace_result)
    pretty_print_model("FINAL INCIDENT REPORT", report_result)


if __name__ == "__main__":
    # 선택: "normal", "db_connection_failure", "traffic_spike", "opensearch_index_delay"
    run_scenario("db_connection_failure")
