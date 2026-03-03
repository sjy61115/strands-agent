# Run-Book: OpenSearch Indexing Delay

## 증상
- IngestionPipeline에서 log ingestion backlog 증가
- OpenSearchIndexer에서 index refresh 지연 경고
- SearchApi에서 최근 로그 검색 불가 경고
- 대시보드/알림에 최신 데이터 미반영
- 인덱싱 지연 시간이 임계값(예: 30초) 초과

## 영향 범위
- 실시간 로그 모니터링 불가 (검색 결과에 최신 데이터 누락)
- 알림 시스템이 최신 이벤트를 감지 못할 수 있음
- 장애 대응 시 실시간 로그 확인 지연

## 즉시 조치
1. OpenSearch 클러스터 상태 확인
   - `GET _cluster/health` → status가 green/yellow/red 확인
   - `GET _cat/nodes?v` → 노드별 CPU, heap, disk 확인
   - `GET _cat/pending_tasks` → 대기 중인 클러스터 태스크 확인
2. Ingestion Pipeline 상태 확인
   - Data Prepper / Logstash / OTel Collector 로그에서 에러 확인
   - 백프레셔(backpressure) 발생 여부 확인
3. 인덱스 refresh interval 조정
   - `PUT /<index>/_settings {"index.refresh_interval": "1s"}` (임시)
   - 주의: refresh 빈도 증가 시 클러스터 부하 증가
4. 불필요한 인덱스 정리
   - 오래된 인덱스 close 또는 delete
   - ISM(Index State Management) 정책 확인

## 후속 조치
1. 클러스터 사이징 재검토
   - 데이터 노드 수 / 인스턴스 타입 업그레이드
   - 샤드 수 최적화 (인덱스당 적정 샤드 크기: 10-50GB)
2. Ingestion 아키텍처 개선
   - 버퍼링 레이어 추가 (SQS/Kafka → OpenSearch)
   - bulk 요청 사이즈 및 flush interval 튜닝
3. Index Template 최적화
   - 불필요한 필드 mapping 제거
   - keyword vs text 타입 재검토
4. 모니터링 강화
   - indexing_latency, refresh_latency 메트릭 알람 설정
   - JVM heap pressure 알람 추가

## 에스컬레이션
- 클러스터 status가 red인 경우: 즉시 인프라 팀 호출
- 1시간 이상 인덱싱 지연 지속: 서비스 PM에게 영향도 공유
