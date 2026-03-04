import json
import os
import requests
from schemas import IncidentReport


def _load_slack_webhook_url() -> str:
    """
    SLACK_WEBHOOK_URL 환경변수 → 없으면 Secrets Manager에서 조회.
    로컬(.env), Docker(환경변수), AgentCore(Secrets Manager) 세 환경 모두 대응.
    """
    url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if url:
        return url

    # Secrets Manager에서 조회 (AgentCore 환경)
    try:
        import boto3
        client = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "ap-northeast-2"))
        response = client.get_secret_value(SecretId="incident-agent/slack-webhook")
        secret = json.loads(response["SecretString"])
        return secret.get("SLACK_WEBHOOK_URL", "")
    except Exception:
        return ""


SLACK_WEBHOOK_URL = _load_slack_webhook_url()

SEVERITY_COLOR = {
    "critical": "#FF0000",
    "high":     "#FF6600",
    "medium":   "#FFCC00",
    "low":      "#36A64F",
}

SEVERITY_EMOJI = {
    "critical": ":red_circle:",
    "high":     ":large_orange_circle:",
    "medium":   ":large_yellow_circle:",
    "low":      ":large_green_circle:",
}


def send_incident_report(report: IncidentReport, scenario: str) -> bool:
    """
    IncidentReport를 Slack Incoming Webhook으로 전송한다.
    SLACK_WEBHOOK_URL 환경변수가 없으면 터미널에 페이로드를 출력하고 종료한다.
    """
    if not SLACK_WEBHOOK_URL:
        print("[slack_notifier] SLACK_WEBHOOK_URL 환경변수가 설정되지 않았습니다.")
        print("[slack_notifier] 아래 페이로드가 Slack으로 전송될 내용입니다:\n")
        _print_report(report, scenario)
        return False

    payload = _build_payload(report, scenario)

    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"[slack_notifier] Slack 전송 성공 (scenario={scenario})")
            return True
        else:
            print(f"[slack_notifier] Slack 전송 실패: {response.status_code} {response.text}")
            return False
    except requests.RequestException as e:
        print(f"[slack_notifier] Slack 전송 중 오류 발생: {e}")
        return False


def _build_payload(report: IncidentReport, scenario: str) -> dict:
    """Slack Block Kit 형식의 메시지 페이로드를 구성한다."""
    emoji = SEVERITY_EMOJI.get(report.severity, ":white_circle:")
    color = SEVERITY_COLOR.get(report.severity, "#CCCCCC")

    immediate = "\n".join(f"• {a}" for a in report.immediate_actions) or "없음"
    follow_up = "\n".join(f"• {a}" for a in report.follow_up_actions) or "없음"
    root_causes = "\n".join(f"• {c}" for c in report.likely_root_causes) or "없음"
    runbooks = (
        "\n".join(
            f"• [{r.source}] {r.section}" for r in report.runbook_references
        )
        or "없음"
    )

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} 장애 감지 알람: {scenario}",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*장애 요약*\n{report.incident_summary}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*심각도*\n{report.severity.upper()}"},
                {"type": "mrkdwn", "text": f"*분석 신뢰도*\n{report.overall_confidence}%"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*영향 범위*\n{report.impact}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*추정 원인*\n{root_causes}",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*즉시 조치*\n{immediate}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*후속 조치*\n{follow_up}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*참조 런북*\n{runbooks}",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Scenario: `{scenario}` | 분석 완료",
                }
            ],
        },
    ]

    return {
        "attachments": [
            {
                "color": color,
                "blocks": blocks,
            }
        ]
    }


def _print_report(report: IncidentReport, scenario: str) -> None:
    """SLACK_WEBHOOK_URL 미설정 시 터미널에 보기 좋게 출력한다."""
    print(f"  시나리오  : {scenario}")
    print(f"  심각도    : {report.severity.upper()}")
    print(f"  신뢰도    : {report.overall_confidence}%")
    print(f"  요약      : {report.incident_summary}")
    print(f"  영향 범위 : {report.impact}")
    print(f"  추정 원인 :")
    for c in report.likely_root_causes:
        print(f"    - {c}")
    print(f"  즉시 조치 :")
    for a in report.immediate_actions:
        print(f"    - {a}")
    print(f"  후속 조치 :")
    for a in report.follow_up_actions:
        print(f"    - {a}")
