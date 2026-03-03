from schemas import IncidentReport


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
