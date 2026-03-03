from schemas import AnalysisResult
from tools.mock_queries import query_logs, query_metrics, query_traces


def test_query_logs_returns_fixture_data():
    result = query_logs(
        service="payment-api",
        start_time="2026-03-01T14:00:00Z",
        end_time="2026-03-01T14:05:00Z",
        scenario="normal",
    )

    assert result["service"] == "payment-api"
    assert result["scenario"] == "normal"
    assert isinstance(result["items"], list)
    assert len(result["items"]) > 0


def test_analysis_result_schema_can_validate():
    payload = {
        "analysis_type": "log",
        "service_name": "payment-api",
        "time_range": {
            "start": "2026-03-01T14:00:00Z",
            "end": "2026-03-01T14:05:00Z"
        },
        "summary": "정상 범위의 로그 흐름입니다.",
        "evidence": [
            {
                "source": "logs",
                "detail": "성공 처리 로그가 다수 확인됨",
                "timestamp": "2026-03-01T14:00:05Z"
            }
        ],
        "suspected_root_cause": [],
        "confidence": 90,
        "severity": "info",
        "recommended_actions": [
            {
                "action": "계속 모니터링 유지",
                "priority": "low"
            }
        ]
    }

    validated = AnalysisResult(**payload)
    assert validated.analysis_type == "log"
    assert validated.confidence == 90


def test_query_metrics_returns_fixture_data():
    result = query_metrics(
        service="payment-api",
        start_time="2026-03-01T14:10:00Z",
        end_time="2026-03-01T14:15:00Z",
        scenario="db_connection_failure",
    )

    assert result["service"] == "payment-api"
    assert result["scenario"] == "db_connection_failure"
    assert isinstance(result["items"], list)
    assert len(result["items"]) > 0


def test_query_traces_returns_fixture_data():
    result = query_traces(
        service="payment-api",
        start_time="2026-03-01T14:10:00Z",
        end_time="2026-03-01T14:15:00Z",
        scenario="db_connection_failure",
    )

    assert result["service"] == "payment-api"
    assert result["scenario"] == "db_connection_failure"
    assert isinstance(result["items"], list)
    assert len(result["items"]) > 0


def test_analysis_result_schema_allows_root_cause_candidates():
    payload = {
        "analysis_type": "metric",
        "service_name": "payment-api",
        "time_range": {
            "start": "2026-03-01T14:10:00Z",
            "end": "2026-03-01T14:15:00Z"
        },
        "summary": "DB 관련 메트릭 이상이 감지되었습니다.",
        "evidence": [
            {
                "source": "metrics",
                "detail": "db_connection_error_rate가 32.0으로 높음",
                "timestamp": "2026-03-01T14:10:00Z"
            }
        ],
        "suspected_root_cause": [
            "DB 연결 실패",
            "커넥션 풀 고갈"
        ],
        "confidence": 92,
        "severity": "high",
        "recommended_actions": [
            {
                "action": "DB 연결 상태 및 풀 설정 점검",
                "priority": "high"
            }
        ]
    }

    validated = AnalysisResult(**payload)
    assert validated.analysis_type == "metric"
    assert len(validated.suspected_root_cause) == 2
