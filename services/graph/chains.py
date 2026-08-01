"""LCEL chains used by tool-calling agents (live pipeline only).

Every chain exported here is invoked via LangChain tools during agent runs.
"""

from __future__ import annotations

from typing import Any, Dict

from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import (
    RunnableAssign,
    RunnableBranch,
    RunnableLambda,
    RunnableParallel,
    RunnablePassthrough,
    RunnableSequence,
)
from pydantic import BaseModel, Field

from services.agents.prompts import (
    CODE_UNDERSTANDING_PROMPT,
    DOCUMENTATION_PROMPT,
    MARKDOWN_PROMPT,
    METADATA_PROMPT,
    PLANNER_PROMPT,
    QUALITY_REVIEW_PROMPT,
    SUPERVISOR_PROMPT,
)
from services.agents.schemas import (
    CodeUnderstandingResult,
    ConversionPlan,
    DocumentationResult,
    MarkdownImprovement,
    MetadataResult,
    QualityReviewResult,
    SupervisorDecision,
)


def _structured_or_json(llm: Any, schema: type[BaseModel]) -> Any:
    try:
        return llm.with_structured_output(schema)
    except Exception:  # noqa: BLE001
        parser = JsonOutputParser(pydantic_object=schema)
        return RunnableLambda(lambda x: x)


def build_planner_chain(llm: Any) -> RunnableSequence:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", PLANNER_PROMPT),
            (
                "human",
                "Notebooks: {notebooks}\nAuto-execute: {auto_execute}\n"
                "PDF settings: {pdf_settings}\nThreshold: {threshold}\nPlan.",
            ),
        ]
    )
    try:
        return prompt | llm.with_structured_output(ConversionPlan)
    except Exception:  # noqa: BLE001
        parser = JsonOutputParser(pydantic_object=ConversionPlan)
        return (
            prompt.partial(format_instructions=parser.get_format_instructions())
            | llm
            | parser
        )


def build_supervisor_chain(llm: Any) -> RunnableSequence:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SUPERVISOR_PROMPT),
            (
                "human",
                "Plan: {plan_steps}\nCompleted: {completed_steps}\n"
                "Quality: {quality}\nValidation: {validation}\n"
                "Needs execution: {needs_execution}\n"
                "Has PDFs: {has_pdfs}\nHas download: {has_download}\n"
                "Repair loops: {repair_loops}/{max_repair_loops}\n"
                "Status: {status}\nError: {error}\nNext agent?",
            ),
        ]
    )
    try:
        return prompt | llm.with_structured_output(SupervisorDecision)
    except Exception:  # noqa: BLE001
        parser = JsonOutputParser(pydantic_object=SupervisorDecision)
        return (
            prompt.partial(format_instructions=parser.get_format_instructions())
            | llm
            | parser
        )


def build_metadata_enrichment_chain(llm: Any) -> RunnableSequence:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", METADATA_PROMPT),
            (
                "human",
                "Filename: {filename}\nTitle: {title}\nDescription: {description}\n"
                "Language: {language}\nCode understanding: {code_understanding}\n"
                "Return improved metadata.",
            ),
        ]
    )
    try:
        return prompt | llm.with_structured_output(MetadataResult)
    except Exception:  # noqa: BLE001
        parser = JsonOutputParser(pydantic_object=MetadataResult)
        return (
            prompt.partial(format_instructions=parser.get_format_instructions())
            | llm
            | parser
        )


def build_insights_chain(llm: Any) -> RunnableSequence:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", CODE_UNDERSTANDING_PROMPT),
            (
                "human",
                "Filename: {filename}\nTitle: {title}\nDescription: {description}\n"
                "Language: {language}\nExcerpt:\n{excerpt}\n",
            ),
        ]
    )
    try:
        return prompt | llm.with_structured_output(CodeUnderstandingResult)
    except Exception:  # noqa: BLE001
        parser = JsonOutputParser(pydantic_object=CodeUnderstandingResult)
        return (
            prompt.partial(format_instructions=parser.get_format_instructions())
            | llm
            | parser
        )


def build_readme_chain(llm: Any) -> RunnableSequence:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", DOCUMENTATION_PROMPT),
            (
                "human",
                "Title: {title}\nDescription: {description}\nLanguage: {language}\n"
                "Filename: {filename}\nKeywords: {keywords}\n"
                "Code understanding: {code_understanding}\nInsights: {insights}\n"
                "Produce README + executive_summary + insights + features.",
            ),
        ]
    )
    try:
        return prompt | llm.with_structured_output(DocumentationResult)
    except Exception:  # noqa: BLE001
        return prompt | llm | StrOutputParser() | RunnableLambda(
            lambda text: {
                "readme_markdown": text,
                "executive_summary": "",
                "insights": [],
                "features": [],
            }
        )


def build_markdown_review_chain(llm: Any) -> RunnableSequence:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", MARKDOWN_PROMPT),
            ("human", "Filename: {filename}\nExcerpt:\n{excerpt}\n"),
        ]
    )
    try:
        return prompt | llm.with_structured_output(MarkdownImprovement)
    except Exception:  # noqa: BLE001
        parser = JsonOutputParser(pydantic_object=MarkdownImprovement)
        return (
            prompt.partial(format_instructions=parser.get_format_instructions())
            | llm
            | parser
        )


def build_quality_review_chain(llm: Any) -> RunnableSequence:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", QUALITY_REVIEW_PROMPT),
            (
                "human",
                "Threshold: {threshold}\nParsed: {parsed_summary}\n"
                "Validation: {validation}\nExecution: {execution}\n"
                "Prior quality: {prior_quality}\nScore and repair decision.",
            ),
        ]
    )
    try:
        return prompt | llm.with_structured_output(QualityReviewResult)
    except Exception:  # noqa: BLE001
        parser = JsonOutputParser(pydantic_object=QualityReviewResult)
        return (
            prompt.partial(format_instructions=parser.get_format_instructions())
            | llm
            | parser
        )


def build_parallel_enrichment(llm: Any) -> RunnableParallel:
    """RunnableParallel used by the lcel_parallel_enrichment tool."""
    return RunnableParallel(
        metadata=build_metadata_enrichment_chain(llm),
        insights=build_insights_chain(llm),
        markdown=build_markdown_review_chain(llm),
    )


def build_status_branch(ok_runnable: Any, err_runnable: Any) -> RunnableBranch:
    return RunnableBranch(
        (lambda x: bool((x or {}).get("ok")), ok_runnable),
        err_runnable,
    )


def build_context_assign() -> RunnableAssign:
    return RunnableAssign(
        {
            "timestamp": RunnableLambda(lambda _: __import__("datetime").datetime.now().isoformat()),
        }
    )


def identity_passthrough() -> RunnablePassthrough:
    return RunnablePassthrough()


def invoke_chain_to_dict(chain: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    result = chain.invoke(payload)
    if isinstance(result, BaseModel):
        return result.model_dump()
    if isinstance(result, dict):
        return result
    return {"raw": str(result)}
