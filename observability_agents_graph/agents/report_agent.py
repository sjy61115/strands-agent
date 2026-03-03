import json
from strands import Agent

from schemas import IncidentReport


class ReportAgent:
    def __init__(self, agent: Agent | None = None):
        self.agent = agent or Agent(
            system_prompt=(
                "당신은 장애 분석 보고서를 작성하는 종합 분석 에이전트다. "
                "입력으로 들어온 로그/메트릭/트레이스 분석 결과만 바탕으로 최종 보고서를 작성하라. "
                "원시 데이터는 보지 않았다고 가정하고, 세 분석 결과 간 공통점과 차이를 비교해 결론을 내려라. "
                "서로 상충하면 confidence가 더 높은 분석을 우선하되, 불확실성도 명시하라. "
                "응답은 반드시 structured_output_model 스키마를 따르라."
            )
        )

    def build_report(
        self,
        log_analysis,
        metric_analysis,
        trace_analysis,
    ) -> IncidentReport:
        def dump_model(model_obj):
            if hasattr(model_obj, "model_dump"):
                return model_obj.model_dump()
            return model_obj.dict()

        prompt = f"""
다음은 동일한 서비스와 시간 범위에 대한 3개의 분석 결과다.

[로그 분석 결과]
{json.dumps(dump_model(log_analysis), ensure_ascii=False, indent=2)}

[메트릭 분석 결과]
{json.dumps(dump_model(metric_analysis), ensure_ascii=False, indent=2)}

[트레이스 분석 결과]
{json.dumps(dump_model(trace_analysis), ensure_ascii=False, indent=2)}

작업:
1. 세 분석 결과를 종합하여 최종 incident_summary를 작성하라.
2. 공통으로 지목되는 원인을 likely_root_causes에 정리하라.
3. 전체 overall_confidence를 0~100으로 판단하라.
4. 최종 severity를 정하라.
5. impact를 한 문장 이상으로 정리하라.
6. immediate_actions와 follow_up_actions를 구분해서 작성하라.
7. evidence_summary에는 세 분석 결과에서 핵심 근거만 짧게 요약하라.

주의:
- raw 로그/메트릭/트레이스는 보지 않았고, 오직 세 분석 결과만 본 상황으로 판단
- 공통 근거가 많으면 confidence를 높게
- 분석 결과가 상충하면 불확실성을 반영
- 즉시 조치는 운영자가 바로 할 수 있는 내용 위주
- 후속 조치는 재발 방지/구조 개선 위주
"""

        result = self.agent(
            prompt,
            structured_output_model=IncidentReport,
        )
        return result.structured_output
