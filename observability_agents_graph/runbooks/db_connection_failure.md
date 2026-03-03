# Run-Book: Database Connection Failure

## 증상
- DatabaseClient에서 connection timeout 발생
- ConnectionPool exhausted 로그 반복
- PaymentRepository에서 query execution 실패 (connection refused)
- RetryHandler의 재시도 횟수 급증
- DB 관련 트레이스 latency 급등 (p99 > 5초)
- 5xx 에러율 급증

## 영향 범위
- payment-api 서비스 전체 트랜잭션 처리 불가
- 결제 요청 실패로 사용자 경험 직접 영향
- 하위 의존 서비스(정산, 알림)까지 연쇄 장애 가능

## 즉시 조치
1. DB 인스턴스 상태 확인
   - RDS 콘솔에서 인스턴스 상태, CPU, 메모리, 디스크 확인
   - `SELECT count(*) FROM pg_stat_activity;` 로 현재 커넥션 수 확인
2. 느린 쿼리 확인 및 종료
   - `SELECT pid, now() - pg_stat_activity.query_start AS duration, query FROM pg_stat_activity WHERE state = 'active' ORDER BY duration DESC;`
   - 장시간 실행 중인 쿼리 kill: `SELECT pg_terminate_backend(<pid>);`
3. 커넥션 풀 임시 증가
   - 애플리케이션의 HikariCP/DBCP 최대 풀 사이즈를 일시적으로 증가
   - 환경변수 또는 ConfigMap 수정 후 rolling restart
4. 트래픽 감소 조치
   - 비핵심 배치 작업 일시 중단
   - Rate limiter 임계값 하향 조정

## 후속 조치
1. slow query 분석 및 인덱스 추가
   - pg_stat_statements에서 mean_exec_time 상위 쿼리 식별
   - EXPLAIN ANALYZE로 실행 계획 확인 후 인덱스 생성
2. 커넥션 풀 설정 최적화
   - maxPoolSize, connectionTimeout, idleTimeout 튜닝
   - 서비스별 적정 커넥션 수 산정
3. Circuit Breaker 패턴 적용
   - DB 접근 경로에 Resilience4j 또는 유사 라이브러리 적용
   - fallback 로직 구현 (캐시 반환 등)
4. DB 모니터링 강화
   - CloudWatch/Prometheus에 커넥션 풀 메트릭 알람 추가
   - 임계치 초과 시 Slack 알림 설정

## 에스컬레이션
- 15분 이내 복구 안 될 경우: DBA 팀 호출
- 30분 이내 복구 안 될 경우: 인프라 팀장 + 서비스 PM 에스컬레이션
