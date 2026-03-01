import json
from strands import Agent

from schemas import AnalysisResult


class TraceAnalysisAgent:
    def __init__(self, agent: Agent | None = None):
        self.agent = agent or Agent(
            system_prompt=(
                "당신은 관측 가능성 플랫폼의 트레이스 분석 전문가다. "
                "입력으로 주어진 트레이스 조회 결과만 바탕으로 병목과 오류 구간을 판단하라. "
                "evidence에는 실제 span, duration, error 내용을 반영하라. "
                "응답은 반드시 structured_output_model 스키마를 따르라."
            )
        )

    def analyze(
        self,
        trace_query_result: dict,
        service: str,
        start_time: str,
        end_time: str,
    ) -> AnalysisResult:
        prompt = f"""
다음은 서비스 트레이스 조회 결과다.

[서비스]
{service}

[시간 범위]
{start_time} ~ {end_time}

[트레이스 결과(JSON)]
{json.dumps(trace_query_result, ensure_ascii=False, indent=2)}

작업:
1. 현재 트레이스 상태를 요약하라.
2. 오류 span 또는 지연 구간을 evidence에 정리하라.
3. 의심 원인 후보를 정리하라.
4. severity와 confidence를 판단하라.
5. recommended_actions를 제안하라.

주의:
- analysis_type은 반드시 "trace"
- service_name은 반드시 "{service}"
- time_range.start는 반드시 "{start_time}"
- time_range.end는 반드시 "{end_time}"
- evidence는 실제 trace/span 정보 기반으로만 작성
- duration이 길고 ERROR가 반복되면 심각도를 높여라
"""

        result = self.agent(
            prompt,
            structured_output_model=AnalysisResult,
        )
        return result.structured_output
