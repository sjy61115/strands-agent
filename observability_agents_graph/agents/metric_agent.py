import json
from strands import Agent

from schemas import AnalysisResult


class MetricAnalysisAgent:
    def __init__(self, agent: Agent | None = None):
        self.agent = agent or Agent(
            system_prompt=(
                "당신은 관측 가능성 플랫폼의 메트릭 분석 전문가다. "
                "입력으로 주어진 메트릭 조회 결과만 근거로 판단하라. "
                "이상 징후가 있으면 요약하고, evidence에는 실제 메트릭 수치만 반영하라. "
                "응답은 반드시 structured_output_model 스키마를 따르라."
            )
        )

    def analyze(
        self,
        metric_query_result: dict,
        service: str,
        start_time: str,
        end_time: str,
    ) -> AnalysisResult:
        prompt = f"""
다음은 서비스 메트릭 조회 결과다.

[서비스]
{service}

[시간 범위]
{start_time} ~ {end_time}

[메트릭 결과(JSON)]
{json.dumps(metric_query_result, ensure_ascii=False, indent=2)}

작업:
1. 현재 메트릭 상태를 요약하라.
2. 비정상 수치가 있으면 evidence에 정리하라.
3. 의심 원인 후보를 정리하라.
4. severity와 confidence를 판단하라.
5. recommended_actions를 제안하라.

주의:
- analysis_type은 반드시 "metric"
- service_name은 반드시 "{service}"
- time_range.start는 반드시 "{start_time}"
- time_range.end는 반드시 "{end_time}"
- evidence는 실제 입력 수치 기반으로만 작성
- 5xx, latency, error rate가 높으면 장애 가능성을 높게 평가
"""

        result = self.agent(
            prompt,
            structured_output_model=AnalysisResult,
        )
        return result.structured_output
