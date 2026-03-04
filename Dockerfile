# AgentCore Runtime 요구사항: linux/arm64
FROM --platform=linux/arm64 python:3.12-slim

WORKDIR /app

# 시스템 패키지 (chromadb ONNX 모델 빌드에 필요)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 패키지 설치 (코드보다 먼저 복사해서 레이어 캐시 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
# observability_agents_graph/ → /app/ 으로 복사
# 결과: /app/handlers/alert_handler.py, /app/orchestrators/incident_graph.py ...
COPY observability_agents_graph/ .

# AgentCore Runtime 포트
EXPOSE 8080

# 실행 시 인자 없이 실행 → AgentCore 서버 모드
CMD ["python", "handlers/alert_handler.py"]
