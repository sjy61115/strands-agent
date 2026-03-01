from typing import Literal, Optional
from pydantic import BaseModel, Field


Severity = Literal["info", "low", "medium", "high", "critical"]
Priority = Literal["low", "medium", "high"]
AnalysisType = Literal["log", "metric", "trace"]


class TimeRange(BaseModel):
    start: str = Field(description="분석 시작 시각 (ISO8601 문자열)")
    end: str = Field(description="분석 종료 시각 (ISO8601 문자열)")


class EvidenceItem(BaseModel):
    source: str = Field(description="근거 출처. 예: logs, metrics, traces, athena, opensearch, amp")
    detail: str = Field(description="근거 상세 설명")
    timestamp: Optional[str] = Field(default=None, description="근거 시각 (있으면 기록)")


class ActionItem(BaseModel):
    action: str = Field(description="권장 조치")
    priority: Priority = Field(description="조치 우선순위")


class AnalysisResult(BaseModel):
    analysis_type: AnalysisType = Field(description="분석 타입")
    service_name: str = Field(description="대상 서비스명")
    time_range: TimeRange = Field(description="분석 시간 범위")
    summary: str = Field(description="핵심 요약")
    evidence: list[EvidenceItem] = Field(default_factory=list, description="판단 근거 목록")
    suspected_root_cause: list[str] = Field(default_factory=list, description="의심 원인 후보")
    confidence: int = Field(ge=0, le=100, description="분석 신뢰도 (0~100)")
    severity: Severity = Field(description="심각도")
    recommended_actions: list[ActionItem] = Field(default_factory=list, description="권장 조치 목록")


class IncidentReport(BaseModel):
    incident_summary: str = Field(description="최종 장애 요약")
    likely_root_causes: list[str] = Field(default_factory=list, description="가장 가능성 높은 원인들")
    overall_confidence: int = Field(ge=0, le=100, description="전체 신뢰도")
    severity: Literal["low", "medium", "high", "critical"] = Field(description="최종 심각도")
    impact: str = Field(description="장애 영향 범위")
    immediate_actions: list[str] = Field(default_factory=list, description="즉시 조치")
    follow_up_actions: list[str] = Field(default_factory=list, description="후속 조치")
    evidence_summary: list[str] = Field(default_factory=list, description="핵심 근거 요약")
