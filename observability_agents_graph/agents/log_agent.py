import json
from strands import Agent

from schemas import AnalysisResult


class LogAnalysisAgent:
    def __init__(self, agent: Agent | None = None):
        self.agent = agent or Agent(
            system_prompt=(
                "당신은 관측 가능성 플랫폼의 로그 분석 전문가다. "
                "입력으로 주어진 로그 조회 결과를 바탕으로만 판단하라. "
                "추측은 최소화하고, evidence에는 실제 로그 근거만 넣어라. "
                "응답은 반드시 structured_output_model 스키마에 맞춰라."
            )
        )

    def analyze(
        self,
        log_query_result: dict,
        service: str,
        start_time: str,
        end_time: str,
    ) -> AnalysisResult:
        prompt = f"""
다음은 서비스 로그 조회 결과다.

[서비스]
{service}

[시간 범위]
{start_time} ~ {end_time}

[로그 결과(JSON)]
{json.dumps(log_query_result, ensure_ascii=False, indent=2)}

작업:
1. 현재 로그 상태를 요약하라.
2. 근거가 되는 로그를 evidence로 정리하라.
3. 의심 원인 후보를 정리하라.
4. severity와 confidence를 판단하라.
5. recommended_actions를 제안하라.

주의:
- analysis_type은 반드시 "log"
- service_name은 반드시 "{service}"
- time_range.start는 반드시 "{start_time}"
- time_range.end는 반드시 "{end_time}"
- evidence는 실제 입력 로그 기반으로만 작성
- 장애 징후가 뚜렷하지 않으면 severity는 info 또는 low
"""

        result = self.agent(
            prompt,
            structured_output_model=AnalysisResult,
        )
        return result.structured_output
