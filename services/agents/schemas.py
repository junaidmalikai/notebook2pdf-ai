"""Typed schemas for AI agent structured decisions."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

AgentName = Literal[
    "notebook_analysis",
    "notebook_execution",
    "code_understanding",
    "markdown",
    "metadata",
    "documentation",
    "image_processing",
    "parallel_enrichment",
    "validation",
    "quality_review",
    "pdf_assembly",
    "packaging",
    "coordinator",
    "FINISH",
]


class ConversionPlan(BaseModel):
    """AI-generated ordered conversion plan."""

    goal: str = Field(description="One-sentence conversion goal")
    needs_execution: bool = Field(
        description="Whether notebooks should be executed before rendering"
    )
    enrich_metadata: bool = True
    improve_markdown: bool = True
    generate_documentation: bool = True
    inventory_images: bool = True
    steps: List[AgentName] = Field(
        description="Ordered worker agent names ending with packaging then FINISH"
    )
    rationale: str = Field(description="Why this plan was chosen")


class SupervisorDecision(BaseModel):
    """Supervisor chooses the next worker."""

    next_agent: AgentName
    reasoning: str
    instructions: str = Field(
        default="",
        description="Short instructions for the next agent",
    )


class CodeUnderstandingResult(BaseModel):
    executive_summary: str
    key_techniques: List[str] = Field(default_factory=list)
    libraries: List[str] = Field(default_factory=list)
    data_flow: str = ""
    risks: List[str] = Field(default_factory=list)


class MarkdownImprovement(BaseModel):
    improved: bool
    notes: str = ""
    quality_score: int = Field(default=70, ge=0, le=100)


class MetadataResult(BaseModel):
    title: str
    description: str
    keywords: List[str] = Field(default_factory=list)
    language: str = "python"


class DocumentationResult(BaseModel):
    readme_markdown: str
    executive_summary: str
    insights: List[str] = Field(default_factory=list)
    features: List[str] = Field(default_factory=list)


class QualityReviewResult(BaseModel):
    score: int = Field(ge=0, le=100)
    passed: bool
    issues: List[str] = Field(default_factory=list)
    repair_agent: Optional[AgentName] = Field(
        default=None,
        description="Agent that should repair issues, or null if passed",
    )
    repair_instructions: str = ""
    summary: str = ""
