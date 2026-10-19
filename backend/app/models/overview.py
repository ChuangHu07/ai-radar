from typing import Literal
from pydantic import Field
from .contracts import StrictModel


class OverviewRequest(StrictModel):
    category_codes: list[str] = Field(min_length=1, max_length=20)
    report_language: Literal['zh', 'en', 'bilingual'] = 'zh'


class Decision(StrictModel):
    paper_id: str
    action: Literal['use_abstract', 'remove']


class Decisions(StrictModel):
    decisions: list[Decision]


class CollectionRequest(StrictModel):
    from_overview_job_id: str | None = None
    selected_paper_ids: list[str] = Field(default_factory=list, max_length=10)


class WorkType(StrictModel):
    primary: str
    secondary: str | None


class Result(StrictModel):
    claim: str
    number: str | None
    compared_to: str | None
    setting: str | None
    source: str
    evidence_ids: list[str]


class Hint(StrictModel):
    direction: str
    route: str
    contribution: str


class Neighbor(StrictModel):
    name: str
    relation: str
    difference: str


class Signals(StrictModel):
    code_available: bool | None
    venue: str | None
    experiment_scale: str | None


class PaperFacts(StrictModel):
    arxiv_id: str
    work_type: WorkType
    problem: str
    why_hard: str
    pain_scenario: str | None
    core_idea: str
    key_mechanism: str
    key_results: list[Result]
    address_hint: Hint
    neighbors: list[Neighbor]
    limitations: str | None
    signals: Signals
    confidence_notes: str
    evidence_ids: list[str]


class Position(StrictModel):
    name: str
    tension: str


class SharedAddress(StrictModel):
    earth: Position
    country: Position
    state: Position | None


class Cluster(StrictModel):
    cluster_id: str
    name: str
    what_is_happening: str
    paper_ids: list[str]


class Relation(StrictModel):
    paper_ids: list[str]
    type: str
    note: str


class Rating(StrictModel):
    arxiv_id: str
    stars: Literal[1, 2, 3, 4, 5]
    reason: str


class BatchMap(StrictModel):
    shared_address: SharedAddress
    map_summary: str
    clusters: list[Cluster]
    highlights: list[str]
    relations: list[Relation]
    ratings: list[Rating]
    reading_order: list[str] | None


class OverviewIssue(StrictModel):
    check: str
    location: str
    problem: str
    fix: str
    severity: Literal['low', 'medium', 'high']


class CardAudit(StrictModel):
    arxiv_id: str
    pass_: bool = Field(alias='pass')
    issues: list[OverviewIssue]


class OverviewAudit(StrictModel):
    results: list[CardAudit]


class CardPatch(StrictModel):
    title: str | None
    plain: str | None
    address: str | None
    one_liner: str | None
    pain: str | None
    trick: str | None
    result: str | None
    so_what: str | None
    caveat: str | None
    tags: str | None
