from schemas import AnalysisResult, IncidentReport, RunbookReference
from tools.mock_queries import query_metrics, query_traces


# ── Metric Agent 관련 테스트 ───────────────────────────────────────────────────

def test_query_metrics_normal_scenario():
    """정상 시나리오에서 metrics 데이터를 올바르게 조회하는지 검증."""
    result = query_metrics(
        service="payment-api",
        start_time="2026-03-01T14:00:00Z",
        end_time="2026-03-01T14:03:00Z",
        scenario="normal",
    )

    assert result["service"] == "payment-api"
    assert result["scenario"] == "normal"
    assert isinstance(result["items"], list)
    assert len(result["items"]) > 0


def test_query_metrics_db_failure_scenario():
    """db_connection_failure 시나리오에서 이상 메트릭이 포함되어 있는지 검증."""
    result = query_metrics(
        service="payment-api",
        start_time="2026-03-01T14:10:00Z",
        end_time="2026-03-01T14:11:00Z",
        scenario="db_connection_failure",
    )

    assert result["scenario"] == "db_connection_failure"
    assert isinstance(result["items"], list)
    assert len(result["items"]) > 0

    metric_names = [item["metric_name"] for item in result["items"]]
    assert "db_connection_error_rate" in metric_names
    assert "db_pool_usage_percent" in metric_names


def test_query_metrics_traffic_spike_scenario():
    """traffic_spike 시나리오에서 metrics 데이터를 올바르게 조회하는지 검증."""
    result = query_metrics(
        service="payment-api",
        start_time="2026-03-01T15:00:00Z",
        end_time="2026-03-01T15:01:00Z",
        scenario="traffic_spike",
    )

    assert result["scenario"] == "traffic_spike"
    assert isinstance(result["items"], list)
    assert len(result["items"]) > 0


def test_metric_analysis_result_schema_high_severity():
    """메트릭 분석 결과가 AnalysisResult 스키마를 통과하는지 검증 (high severity 케이스)."""
    payload = {
        "analysis_type": "metric",
        "service_name": "payment-api",
        "time_range": {
            "start": "2026-03-01T14:10:00Z",
            "end": "2026-03-01T14:11:00Z",
        },
        "summary": "DB 연결 에러율 32%, 커넥션 풀 100% 포화 상태.",
        "evidence": [
            {
                "source": "metrics",
                "detail": "db_connection_error_rate=32.0, db_pool_usage_percent=100",
                "timestamp": "2026-03-01T14:10:00Z",
            }
        ],
        "suspected_root_cause": ["DB 커넥션 풀 고갈", "DB 서버 응답 불가"],
        "confidence": 95,
        "severity": "critical",
        "recommended_actions": [
            {"action": "DB 커넥션 풀 크기 즉시 확장", "priority": "high"}
        ],
    }

    validated = AnalysisResult(**payload)
    assert validated.analysis_type == "metric"
    assert validated.severity == "critical"
    assert validated.confidence == 95
    assert len(validated.suspected_root_cause) == 2


def test_metric_analysis_result_schema_info_severity():
    """정상 메트릭에서 severity가 info로 설정되는지 검증."""
    payload = {
        "analysis_type": "metric",
        "service_name": "payment-api",
        "time_range": {
            "start": "2026-03-01T14:00:00Z",
            "end": "2026-03-01T14:03:00Z",
        },
        "summary": "모든 메트릭이 정상 범위 내에 있습니다.",
        "evidence": [],
        "suspected_root_cause": [],
        "confidence": 98,
        "severity": "info",
        "recommended_actions": [],
    }

    validated = AnalysisResult(**payload)
    assert validated.analysis_type == "metric"
    assert validated.severity == "info"
    assert validated.suspected_root_cause == []


# ── Trace Agent 관련 테스트 ───────────────────────────────────────────────────

def test_query_traces_returns_only_errors_by_default():
    """error_only=True(기본값)일 때 ERROR 상태 트레이스만 반환하는지 검증."""
    result = query_traces(
        service="payment-api",
        start_time="2026-03-01T14:10:00Z",
        end_time="2026-03-01T14:11:00Z",
        scenario="db_connection_failure",
    )

    assert result["scenario"] == "db_connection_failure"
    assert isinstance(result["items"], list)
    assert len(result["items"]) > 0

    for item in result["items"]:
        assert item["status"] == "ERROR"


def test_query_traces_db_failure_contains_db_errors():
    """db_connection_failure 시나리오 트레이스에 DB 관련 에러가 포함되어 있는지 검증."""
    result = query_traces(
        service="payment-api",
        start_time="2026-03-01T14:10:00Z",
        end_time="2026-03-01T14:11:00Z",
        scenario="db_connection_failure",
    )

    error_messages = [item.get("error_message", "") for item in result["items"]]
    db_related = [m for m in error_messages if any(
        keyword in m.lower()
        for keyword in ["database", "connection", "pool", "timeout", "refused"]
    )]
    assert len(db_related) > 0, "DB 관련 에러 메시지가 없음"


def test_query_traces_traffic_spike_scenario():
    """traffic_spike 시나리오에서 traces 데이터를 올바르게 조회하는지 검증."""
    result = query_traces(
        service="payment-api",
        start_time="2026-03-01T15:00:00Z",
        end_time="2026-03-01T15:01:00Z",
        scenario="traffic_spike",
    )

    assert result["scenario"] == "traffic_spike"
    assert isinstance(result["items"], list)
    assert "total" in result


def test_trace_analysis_result_schema_critical():
    """트레이스 분석 결과가 AnalysisResult 스키마를 통과하는지 검증 (critical 케이스)."""
    payload = {
        "analysis_type": "trace",
        "service_name": "payment-api",
        "time_range": {
            "start": "2026-03-01T14:10:00Z",
            "end": "2026-03-01T14:11:00Z",
        },
        "summary": "DB 관련 스팬 3개 모두 ERROR. 커넥션 풀 고갈 확인.",
        "evidence": [
            {
                "source": "traces",
                "detail": "acquire_db_connection span - pool exhausted",
                "timestamp": "2026-03-01T14:10:08Z",
            },
            {
                "source": "traces",
                "detail": "insert_payment_record span - connection refused",
                "timestamp": "2026-03-01T14:10:05Z",
            },
        ],
        "suspected_root_cause": ["DB 커넥션 풀 고갈", "DB 서버 연결 불가"],
        "confidence": 97,
        "severity": "critical",
        "recommended_actions": [
            {"action": "DB 커넥션 풀 즉시 점검", "priority": "high"}
        ],
    }

    validated = AnalysisResult(**payload)
    assert validated.analysis_type == "trace"
    assert validated.severity == "critical"
    assert len(validated.evidence) == 2


def test_trace_analysis_result_schema_empty_traces():
    """트레이스 데이터 없을 때 severity info, 빈 배열 반환하는지 검증."""
    payload = {
        "analysis_type": "trace",
        "service_name": "payment-api",
        "time_range": {
            "start": "2026-03-01T14:00:00Z",
            "end": "2026-03-01T14:03:00Z",
        },
        "summary": "분석 기간 내 트레이스 데이터가 없습니다.",
        "evidence": [],
        "suspected_root_cause": [],
        "confidence": 50,
        "severity": "info",
        "recommended_actions": [],
    }

    validated = AnalysisResult(**payload)
    assert validated.analysis_type == "trace"
    assert validated.severity == "info"
    assert validated.evidence == []


# ── IncidentReport runbook_references 리스트 검증 ────────────────────────────

def test_incident_report_runbook_references_as_list():
    """runbook_references가 리스트 형태로 올바르게 검증되는지 확인."""
    payload = {
        "incident_summary": "DB 커넥션 풀 고갈로 결제 API 전체 장애.",
        "likely_root_causes": ["DB 커넥션 풀 고갈"],
        "overall_confidence": 95,
        "severity": "critical",
        "impact": "결제 요청 전체 실패",
        "immediate_actions": ["DB 커넥션 풀 크기 확장"],
        "follow_up_actions": ["DB 인프라 점검"],
        "evidence_summary": ["db_connection_error_rate=32.0"],
        "runbook_references": [
            {
                "source": "db_connection_failure.md",
                "section": "즉시 조치",
                "relevance": "DB 커넥션 풀 고갈 대응 절차와 직접 일치",
            }
        ],
    }

    validated = IncidentReport(**payload)
    assert isinstance(validated.runbook_references, list)
    assert len(validated.runbook_references) == 1
    assert validated.runbook_references[0].source == "db_connection_failure.md"


def test_incident_report_runbook_references_empty_list():
    """runbook_references가 빈 리스트일 때도 정상 검증되는지 확인."""
    payload = {
        "incident_summary": "정상 상태입니다.",
        "likely_root_causes": [],
        "overall_confidence": 98,
        "severity": "low",
        "impact": "없음",
        "immediate_actions": [],
        "follow_up_actions": [],
        "evidence_summary": [],
        "runbook_references": [],
    }

    validated = IncidentReport(**payload)
    assert isinstance(validated.runbook_references, list)
    assert validated.runbook_references == []
