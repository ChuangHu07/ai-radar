from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReadingRequest(StrictModel):
    collection_id: str
    expected_revision: int
    report_language: Literal["zh", "en", "bilingual"] = "zh"


class EmptyCollection(StrictModel):
    pass


class Narrative(StrictModel):
    zh: str


class Fact(StrictModel):
    fact_id: str
    statement: str
    numbers: list[Annotated[str, Field(pattern=r"^\d[\d,]*(?:\.\d+)?$", description="One numeric token copied from a cited passage, without units, formulas or labels.")]]
    conditions: str
    evidence_ids: list[str]


class Section(StrictModel):
    key: Literal["storyline", "prerequisites", "method", "evidence", "limits", "takeaways"]
    narrative: Narrative
    fact_ids: list[str]
    evidence_ids: list[str]


class ReportDraft(StrictModel):
    title: str
    material_id: str
    sections: list[Section]
    facts: list[Fact]
    warnings: list[str]
