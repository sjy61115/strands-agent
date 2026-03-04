"""
lambda_forwarder.py

SNS → AgentCore Runtime 연결을 위한 경량 Lambda 핸들러.

역할:
  - SNS 이벤트를 파싱해서 알람 딕셔너리를 추출
  - AgentCore Runtime에 HTTP POST로 포워딩

이 Lambda는 비즈니스 로직이 없고 이벤트 중계만 담당하기 때문에
타임아웃이 짧고 (10~30초) 콜드 스타트 부담이 없다.
실제 분석은 AgentCore Runtime (alert_handler.py)에서 수행된다.

필수 환경변수:
  AGENTCORE_RUNTIME_ARN  : AgentCore Runtime ARN
                           (예: arn:aws:bedrock-agentcore:us-east-1:123456789:runtime/my-agent-xxxxx)
  AGENTCORE_SESSION_ID   : 세션 ID (33자 이상, 선택 — 미설정 시 자동 생성)
  AWS_REGION             : AWS 리전 (기본값: us-east-1)

AWS 배포 후 트리거 설정:
  SNS Topic → Lambda(이 파일) → AgentCore Runtime(alert_handler.py)
"""

import json
import os
import uuid

import boto3

AGENTCORE_RUNTIME_ARN = os.environ.get("AGENTCORE_RUNTIME_ARN", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


def _make_session_id() -> str:
    """AgentCore가 요구하는 33자 이상의 세션 ID를 생성한다."""
    custom = os.environ.get("AGENTCORE_SESSION_ID", "")
    if custom and len(custom) >= 33:
        return custom
    return f"incident-session-{uuid.uuid4().hex}"


def handler(event: dict, context: object = None) -> dict:
    """
    Lambda 진입점.

    Parameters
    ----------
    event   : SNS 트리거 이벤트 (Records[0].Sns.Message 에 알람 JSON 포함)
    context : Lambda 런타임 컨텍스트
    """
    if not AGENTCORE_RUNTIME_ARN:
        print("[lambda_forwarder] 오류: AGENTCORE_RUNTIME_ARN 환경변수가 설정되지 않았습니다.")
        return {"statusCode": 500, "body": "AGENTCORE_RUNTIME_ARN not configured"}

    # SNS 이벤트에서 알람 딕셔너리 추출
    raw_message = event["Records"][0]["Sns"]["Message"]
    alert = json.loads(raw_message)

    scenario = alert.get("scenario", "unknown")
    print(f"[lambda_forwarder] SNS 수신 → AgentCore 포워딩 — scenario={scenario}")

    # AgentCore Runtime 호출
    client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)
    response = client.invoke_agent_runtime(
        agentRuntimeArn=AGENTCORE_RUNTIME_ARN,
        runtimeSessionId=_make_session_id(),
        payload=json.dumps(alert).encode(),
    )

    result = json.loads(response["response"].read())
    print(f"[lambda_forwarder] AgentCore 응답: {result}")

    return {"statusCode": 200, "body": json.dumps(result)}
