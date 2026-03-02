import json
from typing import Any, Callable

from strands import Agent
from strands.agent.agent_result import AgentResult, EventLoopMetrics
from strands.multiagent import GraphBuilder
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.multiagent.graph import GraphState

from tools.mock_queries import query_logs, query_metrics, query_traces
from schemas import AnalysisResult, IncidentReport


def all_dependencies_complete(required_nodes: list[str]) -> Callable[[GraphState], bool]:
    """
    Graph에서 어떤 노드가 '모든' 의존 노드 완료 후에만 실행되게 하는 AND 조건.
    문서의 "Waiting for All Dependencies" 패턴 그대로.
    """
    def check(state: GraphState) -> bool:
        return all(
            node_id in state.results and state.results[node_id].status == Status.COMPLETED
            for node_id in required_nodes
        )
    return check


class FixturePrepNode(MultiAgentBase):
    """
    LLM 없이 deterministic하게 fixture를 읽어서 downstream 노드에 전달하는 노드.

    Graph의 "Custom Node Types (MultiAgentBase 확장)" 패턴을 그대로 사용.
    """

    def __init__(self, name: str = "prep"):
        self.id = name  # 세션/식별용
        self.name = name

    async def invoke_async(self, task, invocation_state=None, **kwargs) -> MultiAgentResult:
        # task는 보통 문자열이므로 JSON 파싱을 시도
        if not isinstance(task, str):
            task = str(task)

        try:
            payload = json.loads(task)
        except Exception:
            # 최소 fallback: 문자열 그대로
            payload = {"raw_task": task}

        scenario = payload.get("scenario", "normal")
        service = payload.get("service", "payment-api")
        start_time = payload.get("start_time", "2026-03-01T14:00:00Z")
        end_time = payload.get("end_time", "2026-03-01T14:05:00Z")

        logs = query_logs(service=service, start_time=start_time, end_time=end_time, scenario=scenario)
        metrics = query_metrics(service=service, start_time=start_time, end_time=end_time, scenario=scenario)
        traces = query_traces(service=service, start_time=start_time, end_time=end_time, scenario=scenario)

        prep_output = {
            "service": service,
            "time_range": {"start": start_time, "end": end_time},
            "scenario": scenario,
            "logs": logs,
            "metrics": metrics,
            "traces": traces,
        }

        text = json.dumps(prep_output, ensure_ascii=False, indent=2)

        # MultiAgentBase 노드는 MultiAgentResult를 반환해야 하므로:
        # MultiAgentResult(results={...NodeResult(result=AgentResult...)})
        agent_result = AgentResult(
            stop_reason="end_turn",
            message={"role": "assistant", "content": [{"text": text}]},
            metrics=EventLoopMetrics(),
            state={},
            interrupts=None,
            structured_output=None,
        )

        inner_node_result = NodeResult(
            result=agent_result,
            status=Status.COMPLETED,
            execution_count=1,
        )

        return MultiAgentResult(
            status=Status.COMPLETED,
            results={self.name: inner_node_result},
            execution_count=1,
        )


def build_incident_graph() -> Any:
    """
    Graph 구성:
      prep -> (logs, metrics, traces) -> report
    report는 3개 분석이 모두 완료되어야 실행되도록 AND 조건 edge 적용.
    """
    # 1) 노드(Agent) 준비: structured_output_model을 Agent init에 기본값으로 박아둠
    logs_agent = Agent(
        name="logs_agent",
        system_prompt=(
            "너는 Logs Agent이다.\n"
            "입력에는 이전 노드(prep) 결과로 logs/metrics/traces가 담긴 JSON이 제공된다.\n"
            "그 중 logs만 근거로 분석하고 AnalysisResult 스키마로 구조화해라.\n"
            "- analysis_type은 반드시 'log'\n"
            "- evidence는 실제 logs 내용에서만 뽑아라(추측 금지)\n"
        ),
        structured_output_model=AnalysisResult,
    )

    metrics_agent = Agent(
        name="metrics_agent",
        system_prompt=(
            "너는 Metrics Agent이다.\n"
            "입력에는 이전 노드(prep) 결과로 logs/metrics/traces가 담긴 JSON이 제공된다.\n"
            "그 중 metrics만 근거로 분석하고 AnalysisResult 스키마로 구조화해라.\n"
            "- analysis_type은 반드시 'metric'\n"
            "- evidence는 실제 metrics 내용에서만 뽑아라(추측 금지)\n"
        ),
        structured_output_model=AnalysisResult,
    )

    traces_agent = Agent(
        name="traces_agent",
        system_prompt=(
            "너는 Traces Agent이다.\n"
            "입력에는 이전 노드(prep) 결과로 logs/metrics/traces가 담긴 JSON이 제공된다.\n"
            "그 중 traces만 근거로 분석하고 AnalysisResult 스키마로 구조화해라.\n"
            "- analysis_type은 반드시 'trace'\n"
            "- evidence는 실제 traces 내용에서만 뽑아라(추측 금지)\n"
        ),
        structured_output_model=AnalysisResult,
    )

    report_agent = Agent(
        name="report_agent",
        system_prompt=(
            "너는 Report Generator이다.\n"
            "입력에는 이전 노드들의 결과(Logs/Metrics/Traces 분석 결과)가 JSON으로 포함된다.\n"
            "원시 로그/메트릭/트레이스가 아니라 '분석 결과 3개'만 근거로 IncidentReport를 작성해라.\n"
            "세 결과가 서로 수렴하는 공통 원인을 우선으로 정리하고, 즉시 조치/후속 조치를 구분해라.\n"
        ),
        structured_output_model=IncidentReport,
    )

    # 2) prep 노드(LLM 없이 fixture 로드)
    prep_node = FixturePrepNode(name="prep")

    # 3) GraphBuilder로 그래프 구성 
    builder = GraphBuilder()
    builder.add_node(prep_node, "prep")

    builder.add_node(logs_agent, "logs")
    builder.add_node(metrics_agent, "metrics")
    builder.add_node(traces_agent, "traces")
    builder.add_node(report_agent, "report")

    # prep -> 각 분석
    builder.add_edge("prep", "logs")
    builder.add_edge("prep", "metrics")
    builder.add_edge("prep", "traces")

    # 각 분석 -> report (단, 3개 다 끝나야 report 실행)
    and_condition = all_dependencies_complete(["logs", "metrics", "traces"])
    builder.add_edge("logs", "report", condition=and_condition)
    builder.add_edge("metrics", "report", condition=and_condition)
    builder.add_edge("traces", "report", condition=and_condition)

    # entry point는 prep 하나만
    builder.set_entry_point("prep")

    return builder.build()
