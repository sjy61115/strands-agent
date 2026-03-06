#!/usr/bin/env bash
# destroy_aws.sh
#
# 서울 리전(ap-northeast-2)의 incident-agent 관련 AWS 리소스를 전부 삭제한다.
#
# 사용:
#   chmod +x destroy_aws.sh
#   ./destroy_aws.sh
#
# 삭제 대상:
#   - AgentCore Runtime (incidentAgent)
#   - ECR 리포지토리 (incident-agent)
#   - Secrets Manager (incident-agent/slack-webhook)
#   - IAM 롤 + 인라인 정책 (incident-agentcore-role)

set -e

REGION="ap-northeast-2"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REPO_NAME="incident-agent"
IAM_ROLE_NAME="incident-agentcore-role"
SECRET_NAME="incident-agent/slack-webhook"
AGENTCORE_NAME="incidentAgent"

echo "========================================"
echo " incident-agent AWS 리소스 삭제 시작"
echo " 리전  : ${REGION}"
echo " 계정  : ${ACCOUNT_ID}"
echo "========================================"
echo ""
read -p "정말 모든 리소스를 삭제하시겠습니까? (yes 입력): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "취소되었습니다."
  exit 0
fi

# ── AgentCore Runtime 삭제 ────────────────────────────────────────────────
echo "[1/4] AgentCore Runtime 삭제 중..."
RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes \
  --region "${REGION}" \
  --query "agentRuntimes[?agentRuntimeName=='${AGENTCORE_NAME}'].agentRuntimeId" \
  --output text 2>/dev/null)

if [ -n "$RUNTIME_ID" ] && [ "$RUNTIME_ID" != "None" ]; then
  aws bedrock-agentcore-control delete-agent-runtime \
    --agent-runtime-id "${RUNTIME_ID}" \
    --region "${REGION}" > /dev/null
  echo "[1/4] 삭제 요청 완료: ${RUNTIME_ID} (백그라운드에서 삭제 진행)"
else
  echo "[1/4] AgentCore Runtime 없음 — 건너뜀"
fi

# ── ECR 리포지토리 삭제 ───────────────────────────────────────────────────
echo "[2/4] ECR 리포지토리 삭제 중..."
if aws ecr describe-repositories --repository-names "${REPO_NAME}" --region "${REGION}" > /dev/null 2>&1; then
  aws ecr delete-repository \
    --repository-name "${REPO_NAME}" \
    --force \
    --region "${REGION}" > /dev/null
  echo "[2/4] ECR 삭제 완료: ${REPO_NAME}"
else
  echo "[2/4] ECR 리포지토리 없음 — 건너뜀"
fi

# ── Secrets Manager 삭제 (즉시 삭제) ────────────────────────────────────
echo "[3/4] Secrets Manager 삭제 중..."
if aws secretsmanager describe-secret --secret-id "${SECRET_NAME}" --region "${REGION}" > /dev/null 2>&1; then
  aws secretsmanager delete-secret \
    --secret-id "${SECRET_NAME}" \
    --force-delete-without-recovery \
    --region "${REGION}" > /dev/null
  echo "[3/4] Secrets Manager 삭제 완료: ${SECRET_NAME}"
else
  echo "[3/4] Secrets Manager 없음 — 건너뜀"
fi

# ── IAM 롤 + 인라인 정책 삭제 ────────────────────────────────────────────
echo "[4/4] IAM 롤 삭제 중..."
if aws iam get-role --role-name "${IAM_ROLE_NAME}" > /dev/null 2>&1; then
  # 인라인 정책 먼저 삭제
  POLICIES=$(aws iam list-role-policies \
    --role-name "${IAM_ROLE_NAME}" \
    --query 'PolicyNames[]' --output text 2>/dev/null)
  for POLICY in $POLICIES; do
    aws iam delete-role-policy \
      --role-name "${IAM_ROLE_NAME}" \
      --policy-name "${POLICY}" > /dev/null
    echo "[4/4] 인라인 정책 삭제: ${POLICY}"
  done
  # 롤 삭제
  aws iam delete-role --role-name "${IAM_ROLE_NAME}" > /dev/null
  echo "[4/4] IAM 롤 삭제 완료: ${IAM_ROLE_NAME}"
else
  echo "[4/4] IAM 롤 없음 — 건너뜀"
fi

echo ""
echo "========================================"
echo " 삭제 완료!"
echo " 삭제된 리소스:"
echo "   - AgentCore Runtime : ${AGENTCORE_NAME} (${REGION})"
echo "   - ECR               : ${REPO_NAME} (${REGION})"
echo "   - Secrets Manager   : ${SECRET_NAME} (${REGION})"
echo "   - IAM Role          : ${IAM_ROLE_NAME}"
echo "========================================"
