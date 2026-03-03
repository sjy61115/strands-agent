# Run-Book: Traffic Spike / 과부하

## 증상
- RateLimiter에서 request volume 급증 경고
- ApiGateway upstream response latency 증가
- HTTP 503 Service Unavailable 에러 발생
- CPU/메모리 사용률 급증
- 요청 큐 백로그 증가

## 영향 범위
- 서비스 응답 지연 및 일부 요청 실패 (503)
- 사용자 결제 시도 실패율 증가
- Auto-scaling 완료 전까지 성능 저하 지속

## 즉시 조치
1. Auto-Scaling 상태 확인
   - ECS/EKS 오토스케일링 정책 확인 (target tracking 임계값)
   - 현재 desired/running task 수 확인
   - 수동 스케일아웃: `aws ecs update-service --desired-count <N>`
2. Rate Limiting 강화
   - API Gateway throttling 설정 임시 조정
   - 비인증 요청 또는 특정 IP 대역 차단 검토
3. 캐시 활성화
   - 읽기 요청에 대해 ElastiCache/Redis 캐시 히트율 확인
   - 캐시 TTL 일시 연장으로 DB 부하 경감
4. 비핵심 엔드포인트 임시 차단
   - 헬스체크 이외의 비핵심 API를 feature flag로 비활성화
   - 배치/리포트 등 비실시간 작업 중단

## 후속 조치
1. Auto-Scaling 정책 최적화
   - 스케일아웃 쿨다운 타임 단축
   - 예측 기반 스케일링(Predictive Scaling) 검토
2. Load Test 및 용량 산정
   - 현재 트래픽 대비 최대 처리 용량 재산정
   - k6/Locust로 부하 테스트 후 병목 구간 식별
3. CDN / Edge 캐싱 도입
   - 정적 응답에 대해 CloudFront 캐싱 적용
4. 트래픽 패턴 분석
   - 이상 트래픽(DDoS, 봇) 여부 확인
   - WAF 규칙 추가 검토

## 에스컬레이션
- 스케일아웃 후에도 503 지속 시: 인프라 팀 호출
- DDoS 의심 시: 보안 팀 + AWS Shield Advanced 활성화 검토
