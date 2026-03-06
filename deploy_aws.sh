#!/usr/bin/env bash
# deploy_aws.sh
#
# 서울 리전(ap-northeast-2)에 incident-agent 전체 인프라를 구성한다.
#
# 사용:
#   chmod +x deploy_aws.sh
#   ./deploy_aws.sh
#
# 재실행 안전: 이미 존재하는 리소스는 건너뛴다.
# 필수 조건:
#   - Docker Desktop 실행 중
#   - aws cli 설정 완료 (aws configure)
#   - 프로젝트 루트에 .env 파일 (SLACK_WEBHOOK_URL 포함)

set -e  # 오류 발생 시 즉시 중단

# ── 설정값 ─────────────────────────────────────────────────────────────────
REGION="ap-northeast-2"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REPO_NAME="incident-agent"
IMAGE_TAG="latest"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}:${IMAGE_TAG}"
IAM_ROLE_NAME="incident-agentcore-role"
SECRET_NAME="incident-agent/slack-webhook"
AGENTCORE_NAME="incidentAgent"
ENV_FILE=".env"

echo "========================================"
echo " incident-agent AWS 배포 시작"
echo " 리전  : ${REGION}"
echo " 계정  : ${ACCOUNT_ID}"
echo "========================================"

# ── .env에서 SLACK_WEBHOOK_URL 읽기 ──────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
  echo "[오류] .env 파일을 찾을 수 없습니다: ${ENV_FILE}"
  exit 1
fi
SLACK_WEBHOOK_URL=$(grep SLACK_WEBHOOK_URL "$ENV_FILE" | cut -d'=' -f2-)
if [ -z "$SLACK_WEBHOOK_URL" ]; then
  echo "[오류] .env에 SLACK_WEBHOOK_URL이 없습니다."
  exit 1
fi
echo "[1/7] .env에서 SLACK_WEBHOOK_URL 확인 완료"

# ── Docker 이미지 빌드 ────────────────────────────────────────────────────
echo "[2/7] Docker 이미지 빌드 중..."
docker build -t "${REPO_NAME}" . --quiet
echo "[2/7] 빌드 완료: ${REPO_NAME}:latest"

# ── ECR 리포지토리 생성 (이미 존재하면 건너뜀) ────────────────────────────
echo "[3/7] ECR 리포지토리 확인/생성 중..."
if aws ecr describe-repositories --repository-names "${REPO_NAME}" --region "${REGION}" > /dev/null 2>&1; then
  echo "[3/7] ECR 리포지토리 이미 존재 — 건너뜀"
else
  aws ecr create-repository \
    --repository-name "${REPO_NAME}" \
    --region "${REGION}" \
    --image-scanning-configuration scanOnPush=true > /dev/null
  echo "[3/7] ECR 리포지토리 생성 완료: ${ECR_URI}"
fi

# ── ECR 로그인 + 이미지 push ──────────────────────────────────────────────
echo "[4/7] ECR 로그인 및 이미지 push 중..."
aws ecr get-login-password --region "${REGION}" | \
  docker login --username AWS --password-stdin \
  "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com" 2>/dev/null
docker tag "${REPO_NAME}:latest" "${ECR_URI}"
docker push "${ECR_URI}" --quiet
echo "[4/7] 이미지 push 완료: ${ECR_URI}"

# ── IAM 롤 생성 (이미 존재하면 건너뜀) ───────────────────────────────────
echo "[5/7] IAM 롤 확인/생성 중..."
if aws iam get-role --role-name "${IAM_ROLE_NAME}" > /dev/null 2>&1; then
  echo "[5/7] IAM 롤 이미 존재 — 정책만 업데이트"
else
  aws iam create-role \
    --role-name "${IAM_ROLE_NAME}" \
    --assume-role-policy-document '{
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
        "Action": "sts:AssumeRole"
      }]
    }' > /dev/null
  echo "[5/7] IAM 롤 생성 완료: ${IAM_ROLE_NAME}"
fi

aws iam put-role-policy \
  --role-name "${IAM_ROLE_NAME}" \
  --policy-name incident-agentcore-policy \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": ["bedrock:InvokeModel","bedrock:InvokeModelWithResponseStream"],
        "Resource": "*"
      },
      {
        "Effect": "Allow",
        "Action": [
          "logs:CreateLogGroup","logs:CreateLogDelivery","logs:PutLogEvents",
          "logs:GetLogDelivery","logs:UpdateLogDelivery","logs:DeleteLogDelivery",
          "logs:ListLogDeliveries","logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies","logs:DescribeLogGroups"
        ],
        "Resource": "*"
      },
      {
        "Effect": "Allow",
        "Action": ["ecr:GetAuthorizationToken","ecr:BatchCheckLayerAvailability",
                   "ecr:GetDownloadUrlForLayer","ecr:BatchGetImage"],
        "Resource": "*"
      }
    ]
  }' > /dev/null

aws iam put-role-policy \
  --role-name "${IAM_ROLE_NAME}" \
  --policy-name incident-agentcore-secrets-policy \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Action\": [\"secretsmanager:GetSecretValue\"],
      \"Resource\": \"arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:incident-agent/*\"
    }]
  }" > /dev/null

# Memory 읽기/쓰기 및 Memory 리소스 관리 권한
aws iam put-role-policy \
  --role-name "${IAM_ROLE_NAME}" \
  --policy-name incident-agentcore-memory-policy \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "MemoryDataPlane",
        "Effect": "Allow",
        "Action": [
          "bedrock-agentcore:CreateEvent",
          "bedrock-agentcore:GetEvent",
          "bedrock-agentcore:ListEvents",
          "bedrock-agentcore:RetrieveMemoryRecords",
          "bedrock-agentcore:GetMemoryRecord",
          "bedrock-agentcore:ListMemoryRecords"
        ],
        "Resource": "*"
      },
      {
        "Sid": "MemoryControlPlane",
        "Effect": "Allow",
        "Action": [
          "bedrock-agentcore-control:CreateMemory",
          "bedrock-agentcore-control:GetMemory",
          "bedrock-agentcore-control:ListMemories",
          "bedrock-agentcore-control:UpdateMemory"
        ],
        "Resource": "*"
      }
    ]
  }' > /dev/null

echo "[5/7] IAM 정책 업데이트 완료"

# ── Secrets Manager (이미 존재하면 값만 업데이트) ─────────────────────────
echo "[6/7] Secrets Manager 확인/생성 중..."
if aws secretsmanager describe-secret --secret-id "${SECRET_NAME}" --region "${REGION}" > /dev/null 2>&1; then
  aws secretsmanager put-secret-value \
    --secret-id "${SECRET_NAME}" \
    --secret-string "{\"SLACK_WEBHOOK_URL\": \"${SLACK_WEBHOOK_URL}\"}" \
    --region "${REGION}" > /dev/null
  echo "[6/7] Secrets Manager 값 업데이트 완료"
else
  aws secretsmanager create-secret \
    --name "${SECRET_NAME}" \
    --secret-string "{\"SLACK_WEBHOOK_URL\": \"${SLACK_WEBHOOK_URL}\"}" \
    --region "${REGION}" > /dev/null
  echo "[6/7] Secrets Manager 생성 완료: ${SECRET_NAME}"
fi

# ── AgentCore Runtime 생성 또는 업데이트 ─────────────────────────────────
echo "[7/7] AgentCore Runtime 확인/생성 중..."
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${IAM_ROLE_NAME}"

EXISTING_ID=$(aws bedrock-agentcore-control list-agent-runtimes \
  --region "${REGION}" \
  --query "agentRuntimes[?agentRuntimeName=='${AGENTCORE_NAME}'].agentRuntimeId" \
  --output text 2>/dev/null)

if [ -n "$EXISTING_ID" ] && [ "$EXISTING_ID" != "None" ]; then
  echo "[7/7] 기존 AgentCore Runtime 발견 (${EXISTING_ID}) — 업데이트 중..."
  aws bedrock-agentcore-control update-agent-runtime \
    --agent-runtime-id "${EXISTING_ID}" \
    --agent-runtime-artifact "{
      \"containerConfiguration\": {
        \"containerUri\": \"${ECR_URI}\"
      }
    }" \
    --network-configuration '{"networkMode": "PUBLIC"}' \
    --role-arn "${ROLE_ARN}" \
    --region "${REGION}" > /dev/null
  RUNTIME_ID="${EXISTING_ID}"
else
  echo "[7/7] 새 AgentCore Runtime 생성 중..."
  RUNTIME_ID=$(aws bedrock-agentcore-control create-agent-runtime \
    --agent-runtime-name "${AGENTCORE_NAME}" \
    --agent-runtime-artifact "{
      \"containerConfiguration\": {
        \"containerUri\": \"${ECR_URI}\"
      }
    }" \
    --network-configuration '{"networkMode": "PUBLIC"}' \
    --role-arn "${ROLE_ARN}" \
    --region "${REGION}" \
    --query 'agentRuntimeId' --output text)
fi

# READY 대기
echo "[7/7] AgentCore Runtime READY 대기 중... (최대 3분)"
for i in $(seq 1 6); do
  STATUS=$(aws bedrock-agentcore-control get-agent-runtime \
    --agent-runtime-id "${RUNTIME_ID}" \
    --region "${REGION}" \
    --query 'status' --output text 2>&1)
  echo "      $(date +%H:%M:%S) status=${STATUS}"
  if [ "$STATUS" = "READY" ]; then break; fi
  if [ "$i" = "6" ]; then
    echo "[경고] READY 전환 시간 초과. 나중에 직접 확인하세요."
  fi
  sleep 30
done

RUNTIME_ARN="arn:aws:bedrock-agentcore:${REGION}:${ACCOUNT_ID}:runtime/${RUNTIME_ID}"

echo ""
echo "========================================"
echo " 배포 완료!"
echo "========================================"
echo " ECR URI    : ${ECR_URI}"
echo " Runtime ID : ${RUNTIME_ID}"
echo " Runtime ARN: ${RUNTIME_ARN}"
echo ""
echo " 테스트 명령:"
echo "   source .venv/bin/activate"
echo "   python invoke_agentcore.py db_connection_failure"
echo "========================================"

# invoke_agentcore.py ARN 자동 업데이트
if [ -f "invoke_agentcore.py" ]; then
  sed -i '' \
    "s|AGENT_RUNTIME_ARN = \".*\"|AGENT_RUNTIME_ARN = \"${RUNTIME_ARN}\"|" \
    invoke_agentcore.py
  sed -i '' \
    "s|REGION = \".*\"|REGION = \"${REGION}\"|" \
    invoke_agentcore.py
  echo " invoke_agentcore.py ARN/리전 자동 업데이트 완료"
fi

# ── AgentCore Memory 생성 (이미 존재하면 ID만 조회) ─────────────────────────
echo ""
echo "[ Memory ] AgentCore Memory 확인/생성 중..."
MEMORY_ID=$(aws bedrock-agentcore-control list-memories \
  --region "${REGION}" \
  --query "memories[?contains(id,'incident_memory')].id" \
  --output text 2>/dev/null)

if [ -n "$MEMORY_ID" ] && [ "$MEMORY_ID" != "None" ]; then
  echo "[ Memory ] 기존 Memory 사용: ${MEMORY_ID}"
else
  MEMORY_ID=$(aws bedrock-agentcore-control create-memory \
    --name "incident_memory" \
    --description "AI Observability incident analysis history" \
    --event-expiry-duration 90 \
    --memory-strategies '[{"semanticMemoryStrategy":{"name":"incident_semantic"}}]' \
    --region "${REGION}" \
    --query 'memory.memoryId' --output text 2>&1); EXIT=$?
  if [ $EXIT -ne 0 ] || [ -z "$MEMORY_ID" ]; then
    echo "[ Memory ] Memory 생성 오류: ${MEMORY_ID}"
    MEMORY_ID=""
  fi

  if [ -n "$MEMORY_ID" ]; then
    echo "[ Memory ] 새 Memory 생성 완료: ${MEMORY_ID}"
  else
    echo "[ Memory ] Memory 생성 실패 — 수동으로 생성 후 AGENTCORE_MEMORY_ID 환경변수를 설정하세요."
  fi
fi

if [ -n "$MEMORY_ID" ] && [ "$MEMORY_ID" != "None" ]; then
  # Secrets Manager에 Memory ID 저장 (컨테이너에서 환경변수로 사용)
  aws secretsmanager put-secret-value \
    --secret-id "${SECRET_NAME}" \
    --secret-string "{\"SLACK_WEBHOOK_URL\": \"${SLACK_WEBHOOK_URL}\", \"AGENTCORE_MEMORY_ID\": \"${MEMORY_ID}\"}" \
    --region "${REGION}" > /dev/null
  echo "[ Memory ] Memory ID를 Secrets Manager에 저장했습니다."
  echo ""
  echo " Memory ID  : ${MEMORY_ID}"
  echo " 로컬 테스트 시: export AGENTCORE_MEMORY_ID=${MEMORY_ID}"
fi
