"""
invoke_agentcore.py

AgentCore Runtime에 장애 분석 요청을 보내는 로컬 테스트 스크립트.

사용:
    python invoke_agentcore.py [scenario]
    python invoke_agentcore.py db_connection_failure
    python invoke_agentcore.py traffic_spike
"""

import json
import sys
import uuid

import boto3

AGENT_RUNTIME_ARN = "arn:aws:bedrock-agentcore:ap-northeast-2:526002960031:runtime/incidentAgent-2pffN43rdW"
REGION = "ap-northeast-2"

SCENARIOS = {
    "db_connection_failure": {
        "scenario": "db_connection_failure",
        "service":  "payment-api",
        "startsAt": "2026-03-01T14:10:00Z",
        "endsAt":   "2026-03-01T14:11:00Z",
    },
    "traffic_spike": {
        "scenario": "traffic_spike",
        "service":  "payment-api",
        "startsAt": "2026-03-01T15:00:00Z",
        "endsAt":   "2026-03-01T15:01:00Z",
    },
    "opensearch_index_delay": {
        "scenario": "opensearch_index_delay",
        "service":  "payment-api",
        "startsAt": "2026-03-01T16:00:00Z",
        "endsAt":   "2026-03-01T16:01:00Z",
    },
    "normal": {
        "scenario": "normal",
        "service":  "payment-api",
        "startsAt": "2026-03-01T14:00:00Z",
        "endsAt":   "2026-03-01T14:03:00Z",
    },
}


def invoke(scenario: str) -> dict:
    payload = SCENARIOS[scenario]
    session_id = f"incident-session-{uuid.uuid4().hex}"

    print(f"[invoke] AgentCore 호출 — scenario={scenario}")
    print(f"[invoke] Runtime ARN : {AGENT_RUNTIME_ARN}")
    print(f"[invoke] Session ID  : {session_id}")

    client = boto3.client("bedrock-agentcore", region_name=REGION)
    response = client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        runtimeSessionId=session_id,
        payload=json.dumps(payload).encode(),
    )

    raw = response["response"].read()
    result = json.loads(raw)
    return result


if __name__ == "__main__":
    scenario_arg = sys.argv[1] if len(sys.argv) > 1 else "db_connection_failure"

    if scenario_arg not in SCENARIOS:
        print(f"[invoke] 알 수 없는 시나리오: '{scenario_arg}'")
        print(f"[invoke] 사용 가능: {', '.join(SCENARIOS.keys())}")
        sys.exit(1)

    result = invoke(scenario_arg)
    print(f"\n[invoke] 응답:\n{json.dumps(result, ensure_ascii=False, indent=2)}")
