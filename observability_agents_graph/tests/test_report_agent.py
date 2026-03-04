from schemas import IncidentReport, RunbookReference


def test_incident_report_schema_can_validate():
    payload = {
        "incident_summary": "payment-api에서 DB 연결 장애로 인해 결제 요청 실패가 증가했습니다.",
        "likely_root_causes": [
            "DB 연결 실패",
            "커넥션 풀 고갈"
        ],
        "overall_confidence": 93,
        "severity": "high",
        "impact": "결제 API 응답 지연 및 일부 요청 실패가 발생했습니다.",
        "immediate_actions": [
            "DB 연결 상태 확인",
            "커넥션 풀 설정 점검"
        ],
        "follow_up_actions": [
            "DB 풀 사이즈 재조정",
            "장애 알람 기준 개선"
        ],
        "evidence_summary": [
            "로그에서 connection timeout 및 pool exhausted가 반복됨",
            "메트릭에서 db_connection_error_rate와 5xx 비율 증가",
            "트레이스에서 acquire_db_connection 관련 ERROR span 확인"
        ]
    }

    validated = IncidentReport(**payload)
    assert validated.overall_confidence == 93
    assert validated.severity == "high"
    assert len(validated.likely_root_causes) == 2


def test_incident_report_with_runbook_references():
    """runbook_references가 포함된 IncidentReport 스키마 검증."""
    payload = {
        "incident_summary": "DB 커넥션 풀 고갈로 결제 API 전체 장애.",
        "likely_root_causes": ["DB 커넥션 풀 고갈", "DB 서버 응답 불가"],
        "overall_confidence": 95,
        "severity": "critical",
        "impact": "결제 요청 전체 실패",
        "immediate_actions": [
            "DB 인스턴스 상태 확인",
            "커넥션 풀 임시 증가",
        ],
        "follow_up_actions": [
            "slow query 분석 및 인덱스 추가",
            "Circuit Breaker 패턴 적용",
        ],
        "evidence_summary": ["db_connection_error_rate=32.0", "db_pool_usage_percent=100"],
        "runbook_references": [
            {
                "source": "db_connection_failure.md",
                "section": "즉시 조치",
                "relevance": "DB 커넥션 풀 고갈 대응 절차와 직접 일치",
            },
            {
                "source": "db_connection_failure.md",
                "section": "후속 조치",
                "relevance": "slow query 분석 및 Circuit Breaker 적용 지침 포함",
            },
        ],
    }

    validated = IncidentReport(**payload)
    assert validated.severity == "critical"
    assert isinstance(validated.runbook_references, list)
    assert len(validated.runbook_references) == 2
    assert all(isinstance(r, RunbookReference) for r in validated.runbook_references)
    assert validated.runbook_references[0].source == "db_connection_failure.md"
    assert validated.runbook_references[0].section == "즉시 조치"


def test_incident_report_runbook_references_default_empty():
    """runbook_references를 생략하면 기본값이 빈 리스트인지 검증."""
    payload = {
        "incident_summary": "정상 상태.",
        "likely_root_causes": [],
        "overall_confidence": 98,
        "severity": "low",
        "impact": "없음",
        "immediate_actions": [],
        "follow_up_actions": [],
        "evidence_summary": [],
    }

    validated = IncidentReport(**payload)
    assert isinstance(validated.runbook_references, list)
    assert validated.runbook_references == []
