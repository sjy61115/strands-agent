"""
alert_handler.py

세 가지 실행 모드를 모두 지원한다.

[모드 1] 로컬 CLI 테스트 (시나리오 인자 있을 때)
    python handlers/alert_handler.py db_connection_failure

[모드 2] AgentCore 로컬 서버 (인자 없이 실행, bedrock-agentcore 설치된 경우)
    python handlers/alert_handler.py
    → http://localhost:8080 서버 시작
    → curl -X POST http://localhost:8080/invocations \
         -H "Content-Type: application/json" \
         -d '{"scenario": "db_connection_failure", "service": "payment-api",
              "startsAt": "2026-03-01T14:10:00Z", "endsAt": "2026-03-01T14:11:00Z"}'

[모드 3] Lambda 핸들러 (SNS 트리거 또는 lambda_forwarder.py 경유)
    handler(event, context)  ← Lambda/SNS 시그니처 그대로 유지

AWS 배포 시 SLACK_WEBHOOK_URL 환경변수를 설정해야 한다.
"""

import json
import sys
from pathlib import Path

# handlers/ 폴더에서 직접 실행할 때도 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

# 로컬 개발 시 .env 파일 로드 (없으면 무시)
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from orchestrators.incident_graph import build_incident_graph
from tools.slack_notifier import send_incident_report

# AgentCore SDK가 설치된 경우에만 활성화 (로컬 미설치 시에도 CLI 모드로 동작)
try:
    from bedrock_agentcore.runtime import BedrockAgentCoreApp
    app = BedrockAgentCoreApp()
    _agentcore_available = True
except ImportError:
    app = None
    _agentcore_available = False


# ── 로컬 테스트용 샘플 SNS 이벤트 ─────────────────────────────────────────────
# 실제 Prometheus Alert Manager → SNS 로 전달되는 페이로드 구조와 동일하게 구성
SAMPLE_SNS_EVENTS: dict[str, dict] = {
    "db_connection_failure": {
        "Records": [
            {
                "Sns": {
                    "Message": json.dumps({
                        "alertname": "HighDBConnectionErrorRate",
                        "service":   "payment-api",
                        "severity":  "critical",
                        "scenario":  "db_connection_failure",
                        "startsAt":  "2026-03-01T14:10:00Z",
                        "endsAt":    "2026-03-01T14:11:00Z",
                    })
                }
            }
        ]
    },
    "traffic_spike": {
        "Records": [
            {
                "Sns": {
                    "Message": json.dumps({
                        "alertname": "HighRequestRate",
                        "service":   "payment-api",
                        "severity":  "high",
                        "scenario":  "traffic_spike",
                        "startsAt":  "2026-03-01T15:00:00Z",
                        "endsAt":    "2026-03-01T15:01:00Z",
                    })
                }
            }
        ]
    },
    "opensearch_index_delay": {
        "Records": [
            {
                "Sns": {
                    "Message": json.dumps({
                        "alertname": "OpenSearchIndexLag",
                        "service":   "payment-api",
                        "severity":  "medium",
                        "scenario":  "opensearch_index_delay",
                        "startsAt":  "2026-03-01T16:00:00Z",
                        "endsAt":    "2026-03-01T16:01:00Z",
                    })
                }
            }
        ]
    },
    "normal": {
        "Records": [
            {
                "Sns": {
                    "Message": json.dumps({
                        "alertname": "PeriodicHealthCheck",
                        "service":   "payment-api",
                        "severity":  "info",
                        "scenario":  "normal",
                        "startsAt":  "2026-03-01T14:00:00Z",
                        "endsAt":    "2026-03-01T14:03:00Z",
                    })
                }
            }
        ]
    },
}


# ── 핵심 분석 로직 (모든 모드가 공유) ────────────────────────────────────────

def _parse_sns_event(event: dict) -> dict:
    """SNS Records에서 알람 메시지를 추출한다."""
    raw_message = event["Records"][0]["Sns"]["Message"]
    return json.loads(raw_message)


def _run_incident_analysis(alert: dict) -> dict:
    """
    장애 분석 핵심 로직. Lambda/AgentCore/CLI 세 모드가 모두 이 함수를 호출한다.

    Parameters
    ----------
    alert : 알람 딕셔너리 (scenario, service, startsAt, endsAt 포함)

    Returns
    -------
    dict : statusCode 200(성공) 또는 500(실패)
    """
    scenario   = alert.get("scenario", "normal")
    service    = alert.get("service", "payment-api")
    start_time = alert.get("startsAt", "2026-03-01T14:00:00Z")
    end_time   = alert.get("endsAt",   "2026-03-01T14:05:00Z")

    print(f"[alert_handler] 장애 분석 시작 — scenario={scenario}, service={service}")

    # 1. Incident Graph 실행 (Prep → Logs/Metrics/Traces 병렬 → Report)
    graph = build_incident_graph()
    task  = {
        "scenario":   scenario,
        "service":    service,
        "start_time": start_time,
        "end_time":   end_time,
    }
    result = graph(json.dumps(task, ensure_ascii=False))

    # 2. Report 추출
    report = result.results["report"].get_agent_results()[0].structured_output
    if report is None:
        print("[alert_handler] Report 생성 실패: structured_output이 None")
        return {"statusCode": 500, "body": "Report generation failed"}

    print(f"[alert_handler] 분석 완료 — severity={report.severity}, confidence={report.overall_confidence}%")

    # 3. Slack 전송
    success = send_incident_report(report, scenario)

    return {
        "statusCode": 200 if success else 500,
        "body": json.dumps(
            {
                "scenario":   scenario,
                "severity":   report.severity,
                "confidence": report.overall_confidence,
                "slack_sent": success,
            },
            ensure_ascii=False,
        ),
    }


# ── 모드 1: Lambda 핸들러 (SNS 트리거 또는 lambda_forwarder.py 경유) ──────────

def handler(event: dict, context: object = None) -> dict:
    """
    Lambda 진입점. SNS 이벤트를 파싱한 뒤 _run_incident_analysis를 호출한다.

    Parameters
    ----------
    event   : SNS 트리거 이벤트 (Records[0].Sns.Message 에 알람 JSON 포함)
    context : Lambda 런타임 컨텍스트 (로컬에서는 None)
    """
    print("[alert_handler] 이벤트 수신, 파싱 중...")
    alert = _parse_sns_event(event)
    return _run_incident_analysis(alert)


# ── 모드 2: AgentCore 진입점 (bedrock-agentcore 설치된 경우에만 활성화) ───────

if _agentcore_available:
    @app.entrypoint
    def invoke(payload: dict) -> dict:
        """
        AgentCore 진입점. SNS 파싱 없이 알람 딕셔너리를 직접 받는다.

        payload 예시:
        {
            "scenario": "db_connection_failure",
            "service":  "payment-api",
            "startsAt": "2026-03-01T14:10:00Z",
            "endsAt":   "2026-03-01T14:11:00Z"
        }
        """
        print("[alert_handler] AgentCore 요청 수신...")
        return _run_incident_analysis(payload)


# ── 직접 실행 시 모드 분기 ────────────────────────────────────────────────────

if __name__ == "__main__":
    scenario_arg = sys.argv[1] if len(sys.argv) > 1 else None

    if scenario_arg:
        # ── 모드 1: CLI 테스트 (python handlers/alert_handler.py db_connection_failure)
        if scenario_arg not in SAMPLE_SNS_EVENTS:
            available = ", ".join(SAMPLE_SNS_EVENTS.keys())
            print(f"[alert_handler] 알 수 없는 시나리오: '{scenario_arg}'")
            print(f"[alert_handler] 사용 가능한 시나리오: {available}")
            sys.exit(1)

        print(f"[alert_handler] 로컬 테스트 시작 — scenario={scenario_arg}")
        response = handler(SAMPLE_SNS_EVENTS[scenario_arg])
        print(f"\n[alert_handler] 최종 응답: {response}")

    elif _agentcore_available:
        # ── 모드 2: AgentCore 서버 (python handlers/alert_handler.py)
        print("[alert_handler] AgentCore 서버 시작 — http://localhost:8080")
        print("[alert_handler] curl 테스트 예시:")
        print("  curl -X POST http://localhost:8080/invocations \\")
        print('    -H "Content-Type: application/json" \\')
        print('    -d \'{"scenario":"db_connection_failure","service":"payment-api",\'')
        print('         \'"startsAt":"2026-03-01T14:10:00Z","endsAt":"2026-03-01T14:11:00Z"}\'')
        app.run()

    else:
        # bedrock-agentcore 미설치 환경 → db_connection_failure 기본 실행
        print("[alert_handler] bedrock-agentcore 미설치 → CLI 모드로 실행합니다.")
        print("[alert_handler] 설치: pip install bedrock-agentcore")
        print("[alert_handler] 기본 시나리오(db_connection_failure)로 실행합니다.\n")
        response = handler(SAMPLE_SNS_EVENTS["db_connection_failure"])
        print(f"\n[alert_handler] 최종 응답: {response}")
