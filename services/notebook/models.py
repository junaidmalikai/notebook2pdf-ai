"""Typed models for Jupyter notebook content."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CellType(str, Enum):
    MARKDOWN = "markdown"
    CODE = "code"
    RAW = "raw"


class OutputType(str, Enum):
    STREAM = "stream"
    EXECUTE_RESULT = "execute_result"
    DISPLAY_DATA = "display_data"
    ERROR = "error"


@dataclass
class NotebookOutput:
    output_type: OutputType
    text: str = ""
    html: str = ""
    images: List[Dict[str, str]] = field(default_factory=list)  # [{mime, data_b64}]
    name: str = ""  # stdout / stderr
    ename: str = ""
    evalue: str = ""
    traceback: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NotebookCell:
    cell_type: CellType
    source: str
    execution_count: Optional[int] = None
    outputs: List[NotebookOutput] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    hidden: bool = False
    collapsed: bool = False
    index: int = 0

    @property
    def heading_level(self) -> Optional[int]:
        if self.cell_type != CellType.MARKDOWN:
            return None
        for line in self.source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                level = 0
                for ch in stripped:
                    if ch == "#":
                        level += 1
                    else:
                        break
                if 1 <= level <= 6 and stripped[level : level + 1] in ("", " "):
                    return level
        return None

    @property
    def heading_text(self) -> Optional[str]:
        level = self.heading_level
        if not level:
            return None
        for line in self.source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#" * level):
                return stripped[level:].strip().lstrip("#").strip()
        return None


@dataclass
class NotebookDocument:
    filename: str
    cells: List[NotebookCell]
    metadata: Dict[str, Any] = field(default_factory=dict)
    nbformat: int = 4
    title: str = ""
    description: str = ""
    language: str = "python"

    @property
    def code_cell_count(self) -> int:
        return sum(1 for c in self.cells if c.cell_type == CellType.CODE)

    @property
    def markdown_cell_count(self) -> int:
        return sum(1 for c in self.cells if c.cell_type == CellType.MARKDOWN)

    def visible_cells(self) -> List[NotebookCell]:
        return [c for c in self.cells if not c.hidden]
