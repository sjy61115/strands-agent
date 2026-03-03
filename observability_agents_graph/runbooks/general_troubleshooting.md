# Run-Book: General Troubleshooting Guide

## 공통 초기 대응 절차
1. 알림 수신 시 즉시 확인 사항
   - 어떤 서비스에서 발생했는가
   - 언제부터 시작되었는가 (타임라인)
   - 영향 받는 사용자/트래픽 규모
   - 관련 배포가 최근에 있었는가

2. 관찰 가능성 데이터 수집
   - Logs: OpenSearch에서 해당 시간대 ERROR/WARN 로그 검색
   - Metrics: Prometheus/Grafana에서 CPU, 메모리, latency, error rate 확인
   - Traces: 실패한 요청의 trace를 추적하여 병목 구간 식별

## 공통 즉시 조치
1. 최근 배포 롤백 검토
   - 최근 30분 이내 배포가 있었다면 롤백 우선 고려
   - `kubectl rollout undo deployment/<name>` 또는 ECS 이전 task definition 재배포
2. 서비스 재시작
   - 메모리 릭 또는 상태 오류 의심 시 rolling restart
   - 전체 중단 없이 인스턴스 순차 재시작
3. 트래픽 우회
   - 특정 인스턴스 문제 시 로드밸런서에서 제외
   - 장애 리전에서 타 리전으로 DNS failover

## 커뮤니케이션
- 장애 인지 5분 이내: 장애 채널(Slack #incident)에 초기 상황 공유
- 15분마다: 진행 상황 업데이트
- 복구 후: 사후 분석(Post-mortem) 일정 잡기

## 심각도 판단 기준
| 심각도 | 기준 | 대응 시간 |
|--------|------|-----------|
| critical | 서비스 전면 중단, 데이터 유실 위험 | 즉시 |
| high | 주요 기능 장애, 다수 사용자 영향 | 15분 이내 |
| medium | 일부 기능 저하, 제한적 영향 | 1시간 이내 |
| low | 성능 저하, 모니터링 이상 | 업무 시간 내 |

## 에스컬레이션 매트릭스
- L1 (온콜 엔지니어): 모든 알림 초기 대응
- L2 (시니어/팀리드): 15분 이내 해결 안 될 경우
- L3 (아키텍트/VP): critical 장애 30분 이상 지속 시
