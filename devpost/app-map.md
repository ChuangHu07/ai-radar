# AI Radar — App Map

The browser handles interaction. FastAPI coordinates sources, materials, generation, and evidence. This map describes actual source locations; it is not evidence that a learner has independently mastered every module.

```mermaid
flowchart TD
    Home[Category search and shortcuts] --> API[FastAPI routes]
    API --> Source[Official arXiv metadata and PDF acquisition]
    Source --> Decision{Sources ready?}
    Decision -->|Full text available| Overview[Evidence and fixed overview cards]
    Decision -->|User accepts abstract-only overview| Overview
    Decision -->|User removes failed source| Overview
    Overview --> Picker[Top-level paper picker]
    Picker --> Materials[Editable reading collection]
    Upload[User PDF upload] --> Materials
    Materials --> Ready{Every final paper ready?}
    Ready -->|No| Repair[Replace or remove failed material]
    Repair --> Materials
    Ready -->|User clicks Generate Report| Job[Single or joint reading job]
    Job --> Checks[Format, source and quality checks]
    Checks -->|Pass| Report[Structured report and source excerpts]
    Checks -->|Fail| Retry[Visible reason, regenerate or exit]
    Report --> Language[Same-material language conversion]
```

## A small debugging route

1. Start at the generation control in `frontend/src/pages/` and inspect its API request.
2. Find the route in `backend/app/main.py`; check material revision, readiness, language and idempotency before blaming the model.
3. Follow the job into `backend/app/reading/`; distinguish acquisition failure, malformed output, missing evidence, and a quality-review finding.
4. Inspect the exact current report sentence and retained source excerpt/page. A reviewer's description may refer to an earlier draft or misread a formula.
5. Repair the responsible layer, run relevant checks, then verify the actual UI behavior. A passing parser test is not a passing real report.

## Ownership and boundaries

Frontend tasks cover navigation, paper selection, language controls, failure states, rendering and evidence inspection. Backend tasks cover category/date mapping, PDF limits, source identity, processing coverage, provider contracts and job safety. Both collaborators check their interface contract and integrated behavior. Keep each machine's environment and credentials local.

Normal collections and reports belong to a temporary backend session. Persisted shortcuts/settings and saved developer review artifacts are different stores. Do not confuse the static public demonstration player with live model access.
