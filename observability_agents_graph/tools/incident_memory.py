"""incident_memory.py

AgentCore Memory 연동 모듈.

역할:
  - 장애 분석 결과를 Bedrock AgentCore Memory에 저장한다.
  - Report Agent에 session_manager를 제공해 과거 유사 장애를 자동으로 컨텍스트로 주입한다.

Memory 전략:
  - semanticMemoryStrategy: LLM이 대화에서 핵심 패턴/인사이트를 추출·저장한다.
  - actor_id = "incident-agent/{service}": 서비스별 독립 메모리로 축적된다.
  - session_id = 장애 1건 = 1세션: 각 장애가 하나의 에피소드로 기록된다.

환경변수:
  - AGENTCORE_MEMORY_ID: 기존 Memory ID (없으면 자동 생성 후 로그 출력)
  - AWS_DEFAULT_REGION: 리전 (기본 ap-northeast-2)
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

MEMORY_NAME = "incident_memory"
REGION = os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2")


def _get_memory_client():
    """MemoryClient 인스턴스를 반환한다. 실패 시 None."""
    try:
        from bedrock_agentcore.memory.client import MemoryClient

        return MemoryClient(region_name=REGION)
    except Exception as e:
        logger.warning("[incident_memory] MemoryClient 초기화 실패: %s", e)
        return None


def _load_memory_id_from_secrets() -> Optional[str]:
    """Secrets Manager에서 AGENTCORE_MEMORY_ID를 조회한다 (AgentCore 배포 환경용)."""
    try:
        import json
        import boto3

        client = boto3.client(
            "secretsmanager",
            region_name=os.environ.get("AWS_REGION", REGION),
        )
        response = client.get_secret_value(SecretId="incident-agent/slack-webhook")
        secret = json.loads(response["SecretString"])
        return secret.get("AGENTCORE_MEMORY_ID")
    except Exception:
        return None


def get_or_create_memory_id(client=None) -> Optional[str]:
    """
    우선순위: 환경변수 → Secrets Manager → Memory 목록 조회 → 신규 생성.

    Returns:
        memory_id 문자열, 실패 시 None
    """
    memory_id = os.getenv("AGENTCORE_MEMORY_ID")
    if memory_id:
        return memory_id

    # AgentCore 배포 환경: Secrets Manager에서 조회
    memory_id = _load_memory_id_from_secrets()
    if memory_id:
        logger.info("[incident_memory] Secrets Manager에서 Memory ID 로드: %s", memory_id)
        return memory_id

    if client is None:
        client = _get_memory_client()
    if client is None:
        return None

    try:
        # 기존 메모리 검색
        memories = client.list_memories()
        for mem in memories:
            if mem.get("name") == MEMORY_NAME:
                found_id = mem.get("memoryId") or mem.get("id")
                if found_id:
                    logger.info("[incident_memory] 기존 Memory 사용: %s", found_id)
                    return found_id

        # 없으면 새로 생성 (semantic 전략: 대화에서 핵심 인사이트 자동 추출)
        memory = client.create_memory(
            name=MEMORY_NAME,
            description="AI Observability 장애 분석 이력 — 서비스별 장애 패턴 축적",
            strategies=[
                {
                    "semanticMemoryStrategy": {
                        "name": "incident_semantic",
                    }
                }
            ],
            event_expiry_days=90,
        )
        new_id = memory.get("memoryId") or memory.get("id")
        logger.info("[incident_memory] 새 Memory 생성 완료: %s", new_id)
        logger.info(
            "[incident_memory] 다음 배포 전 환경변수를 설정하면 재생성을 방지할 수 있습니다: "
            "AGENTCORE_MEMORY_ID=%s",
            new_id,
        )
        return new_id

    except Exception as e:
        logger.warning("[incident_memory] Memory ID 조회/생성 실패 (무시): %s", e)
        return None


def create_report_session_manager(service: str, session_id: str):
    """
    Report Agent에 전달할 AgentCoreMemorySessionManager를 생성한다.

    - actor_id를 서비스 단위로 구성해 동일 서비스의 과거 장애 패턴이 누적된다.
    - long-term memory(semantic)에서 관련 과거 인사이트를 자동으로 주입한다.
    - 새 분석 대화가 끝나면 자동으로 이번 세션을 저장해 다음 분석에 활용된다.

    Args:
        service: 장애 대상 서비스명 (예: "payment-api")
        session_id: 이번 장애의 고유 세션 ID

    Returns:
        AgentCoreMemorySessionManager 인스턴스, 실패 시 None
    """
    try:
        from bedrock_agentcore.memory.integrations.strands import AgentCoreMemorySessionManager
        from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig, RetrievalConfig

        client = _get_memory_client()
        memory_id = get_or_create_memory_id(client)

        if not memory_id:
            logger.warning("[incident_memory] memory_id 없음 — session_manager 없이 실행합니다.")
            return None

        actor_id = f"incident-agent/{service}"

        config = AgentCoreMemoryConfig(
            memory_id=memory_id,
            session_id=session_id,
            actor_id=actor_id,
            # long-term memory에서 상위 3건 컨텍스트 주입
            retrieval_config={
                f"/strategies/*/actors/{actor_id}/": RetrievalConfig(top_k=3)
            },
            context_tag="past_incident_context",
        )

        session_manager = AgentCoreMemorySessionManager(
            agentcore_memory_config=config,
            region_name=REGION,
        )

        logger.info(
            "[incident_memory] session_manager 생성 완료 — memory_id=%s, actor=%s, session=%s",
            memory_id,
            actor_id,
            session_id,
        )
        return session_manager

    except Exception as e:
        logger.warning("[incident_memory] session_manager 생성 실패 (무시): %s", e)
        return None
