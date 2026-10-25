# AI Radar

Discover recent research. Understand what it means.

## Inspiration and audience

Finding a paper and understanding it are different challenges. AI Radar is for researchers and students entering an unfamiliar field who want to understand what a paper does before deciding whether to study it deeply.

## What it does

Search an official arXiv category to explore up to five recent papers. Each overview starts with a plain-language problem and the authors' change, followed by research context, technical detail, evidence and limitations. Concrete illustrations help explain the ideas and are labeled as concept illustrations, not experimental results.

The top-level deep-reading control opens a compact paper picker. Readers can select papers from the overview or upload their own PDFs, then edit the final collection. One paper produces a learning guide; two to ten produce a joint report comparing research questions, methods, evidence and limitations. Failed materials must be replaced or removed before deep reading begins.

Clicking a source reference reveals its original excerpt, paper and physical PDF page. The interface supports English and Chinese; reports support English, Chinese or both independently of the interface language.

## How we built it

We used the Devpost Learn Skill Pack's questions to discuss and decide the requirements, then worked through scope, PRD, technical specification, implementation and feedback. We put ourselves in the users' shoes when discussing which features to add and how to design them.

The application uses a React/TypeScript frontend and a Python/FastAPI backend, with official arXiv acquisition, PDF parsing, explicit model-provider configuration and structured report generation. Versioned materials, source identifiers, format/number checks and independent model review help detect incomplete or unsupported outputs. These checks support source inspection; they do not certify scientific correctness.

## Challenges and iterations

The first explanations were too technical and the first diagrams too abstract. Team feedback led to problem-first explanations, more concrete scenes and a clearer broad-to-narrow research position. Repeated per-paper action panels were replaced with a single top-level picker.

Formula rendering, unreliable source-number matches and mistaken model-review findings required separate format and evidence checks. Usage limits also prompted a move to a cheaper configured provider, with explicit starts, compatible stage reuse and bounded retries to control repeated work.

## Validation and limitations

The demo shows real application views and previously generated reports. It explicitly identifies the separate two-paper joint-reading example; it is an edited walkthrough, not a fresh uninterrupted generation. Narration is neural synthetic speech with English captions.

Recorded Windows verification passed 216 backend tests and the production frontend build on October 18. Tests use synthetic fixtures and mocked calls and are separate from scientific validation. The current evidence includes first-party team feedback; additional real feedback is reported by the owner but participant context and observations have not yet been documented here. We do not claim measured time savings, learning gains or universal model accuracy.

New generation requires local setup and a valid provider key. Normal sessions are temporary; scanned PDFs/OCR and production multi-user hosting are not supported. PDFs are limited to 50 MiB and 150 pages each. macOS instructions are supplied, but hardware validation remains optional and unperformed. The public demo page hosts the video, not a live AI service.

## What we learned

Building AI Radar taught us how to describe requirements precisely and understand the software development process. Our biggest challenge was turning a vague idea into a clear plan and breaking a large feature into smaller, manageable parts. We learned to move from an idea to defined requirements, then to implementation, testing, and refinement.

## Next steps

Document the existing feedback reported by the owner, with anonymous context and actual observations, before making broader impact claims. Additional independent sessions are optional follow-up work. Cloud deployment and personal-website integration are deferred so the current submission can focus on the working prototype and evidence. Saved libraries, topic updates and shared workspaces are possible later features requiring user validation.

## Project links

- English demo: https://youtu.be/1sG9wfRfSuk
- Public source and MIT license: https://github.com/ChuangHu07/ai-radar
- English scope, PRD and technical specification: https://github.com/ChuangHu07/ai-radar/tree/main/devpost
- Validation protocol and first-party evidence: https://github.com/ChuangHu07/ai-radar/blob/main/devpost/user-validation.md

- Submission requirements review: https://github.com/ChuangHu07/ai-radar/blob/main/devpost/submission-review.md
