# AI Radar — Developer Evaluation and Same-Paper Comparison

Date: October 25, 2026. Operator: the development assistant, using the owner's approved requirements. **No new external participants were recruited.** This is an AI-assisted engineering check and qualitative comparison, not independent user research, a blinded study, or a scientific accuracy certification. Earlier owner-reported hands-on feedback remains a separate evidence source.

## Protocol fixed before generation

The production arXiv client retrieved the first five `cs.AI` results using a frozen cutoff of **2026-10-25 15:18:53 UTC**. All five official PDFs downloaded and passed parsing: **48, 9, 27, 29 and 24 pages; 137 pages total**. No paper was silently removed, substituted or reduced to an abstract. IDs, official URLs, dates and SHA-256 hashes are in [the source manifest](evidence-2026-10-25/sources.json).

The first run used the production overview function with an empty stage cache. For a direct-chat comparison, the configured **qwen3.8-flash** model received the exact same 48-page first PDF and one reasonable novice-reading prompt requesting the problem, method, findings, significance, limitations, broad-to-narrow context, a helpful concrete example and PDF page references. It was not given the app's evidence packets. The baseline completed in one call; it was not selected from multiple attempts. [Protocol and complete prompt](evidence-2026-10-25/protocol.json).

## Actual outcomes, including failures

| Check | Observed result |
|---|---|
| First evaluation-harness attempt | Windows console encoding rejected a Chinese progress label before any app model call. The harness was switched to UTF-8; frozen PDFs and the already generated baseline were retained. Production code was unchanged at this point. |
| First actual app pipeline attempt | **Failed** after 740.375 seconds and 31 model calls. A result rendered a source-table value of `-45.3` as an unsigned decrease of `45.3`; the strict source-number check rejected it. The numeric patch path also exited after its first rejected patch. No complete report was published. |
| Fix | The scoped repair request now explicitly preserves source signs. Its patch validation gets at most two attempts, recording rejection details. Citation, numerical, source-scope and complete-report gates remain in place. |
| Recovery of the identical five-paper batch | **Succeeded** in 266.563 seconds and 18 calls. It reused the exact-hash source packs, accepted facts, batch map and three validated cards. The fourth card was repaired and the remaining card generated; subsequent audit repairs and scene generation still ran. This is a cached recovery, not a second cold-start success. |
| Recovered coverage and visuals | All five papers retained, all 137 physical pages represented in the source packs, fixed card fields present, and all five concept illustrations generated. Full extractable text was processed; this does not mean every chart pixel or every scientific claim was understood correctly. |
| Regression tests | **218 passed in 6.24 seconds** in the isolated public checkout. The two new tests cover a successful second signed-number patch and exhaustion without publishing an invalid result. Mocked tests do not establish real-model accuracy. |
| Frontend | Production build passed. The previously documented bundle-size warning remains. |

The earlier failed attempt and recovery results are both retained. Local usage estimates for this evaluation total **CNY 1.7186063**, comprising the one-call baseline, failed app attempt and recovery. The cumulative development ledger reached **CNY 22.3390132** against the owner's CNY 100 ceiling. These are local estimates, not an invoice or provider balance.

The initial app attempt took approximately 12 minutes 20 seconds; recovery added approximately 4 minutes 27 seconds. Those are generation-stage wall times, excluding acquisition, harness setup and later UI inspection. This batch provides no basis for a general success rate or an instant-generation claim.

## Same-paper comparison

Paper: **Direct Pass@$k$ Optimization for Thought Pruning: Balancing Quality and Diversity in Test-Time Reasoning**, arXiv `2610.31667v1`, 48 pages. Both outputs used the PDF with SHA-256 `77a829330ee555a5652e87a0c5473344b974499251c33e9001c64a5404dc55b0`.

| Requirement from the owner's design | Direct-chat output in this run | Recovered application card |
|---|---|---|
| Explain the problem before technical detail | Yes: introduces the cost of completing many candidate solutions and the quality/diversity trade-off. | Yes: begins with apparently reliable paths that fail together versus diverse but poor paths. |
| Locate the contribution within its field | Provides background in test-time scaling and pruning. | Adds a dedicated broad-to-narrow research-position field. Neither form proves novice comprehension. |
| Explain the method | Useful explanation of latent Gaussian dependence, submodularity and greedy selection. | Gives the same main ideas in fixed plain-language and technical sections. The app is not shown to invent a better explanation than the model. |
| Ground a result | Gives qualitative comparisons and prose page references. | Gives the specific model and budget condition: at `k=4`, 3.0 and 3.2 percentage-point gains over the two baselines, linked to E0026 on physical PDF page 11. The page text was separately inspected for this check. |
| Inspect the evidence | Page references help the reader locate claims manually. It supplied no excerpt interface. | Clicking E0026 opened the original excerpt, focused its summary and retained a source link. This is an observed workflow difference. |
| Visual explanation | Text-only response; no diagram was requested from a separate image tool. | A concept illustration was generated and loaded. This compares product capabilities, not the underlying model's ability to draw. |
| Limits and cautious language | Includes limitations, but calls the quality/diversity balance “perfect”; the inspected passages support a trade-off and empirical gains, not universal perfection. | Has a dedicated caveat and source warnings. Automated auditing and citations do not guarantee scientific correctness. |

The baseline is a useful output, not an intentionally weak strawman. It completed in **92.844 seconds**, with 578 reported output tokens and 1,049 Unicode characters including Markdown. Its local cost estimate was CNY 1.1080054. The app processed five papers through multiple stages and text extraction, while the baseline used one native PDF request; **their time, token and cost totals are not comparable measures of efficiency**.

The supported conclusion is limited: this sample demonstrates the app's consistent structure, explicit material control, illustrations and inspectable evidence workflow. It does **not** demonstrate superior comprehension, higher overall factual accuracy, measured time savings, willingness to pay, or superiority over other products. [Baseline in Chinese](evidence-2026-10-25/baseline-zh.md) and [English translation](evidence-2026-10-25/baseline-en.md).

## Task-based checks in the actual frontend

The newly generated batch was loaded into the existing frontend for inspection; this step did not trigger another generation. English interface and Chinese report content were deliberately kept distinct.

1. Opened the first paper's details and clicked E0026. The source disclosure opened with the matching excerpt and physical page 11; focus moved to its summary.
2. Scrolled through the batch. All five images loaded, with concept-illustration labels.
3. Opened the top-level picker and selected the 48-page and 9-page papers. Their correct titles, IDs and page counts appeared as two ready materials in joint mode.
4. Removed the 9-page material. The workspace changed to single-paper mode with the correct 48-page source retained.
5. Uploaded the same 9-page PDF through the normal file control. It appeared as an uploaded source and restored joint mode. The automation's file-transfer step took unusually long; this does not establish normal user upload latency. No extra generation was started.

These actions check operation and identity transfer. They do not test an external person's understanding or establish that every language variant or every failure path works on these new papers. Earlier translation/joint-reading checks and the existing regression suite remain separate evidence.

## Remaining weaknesses

- Generation latency and the need for explicit recovery remain material limitations. One repaired batch is not a broad reliability benchmark.
- Source-location heuristics sometimes conservatively omit potentially valid results. Rejection is not proof that the paper's claim was wrong.
- Readability still varies: technical terms remain, and some new scenes are more symbolic than the previously accepted concrete examples.
- No fresh single-paper or joint-report generation, new English/bilingual translation, macOS hardware run or new external user session was performed in this evaluation.
- No human comprehension score, productivity gain or market demand has been measured.

## Final English presentation

The final **2:50 English main video** combines the existing approved narration with actual selection, collection-editing and citation-opening actions. It starts with motivation, covers the layout and major features, then closes with the team's learning and product value. It uses saved reports and explicitly labels the separate joint example; it does not claim a fresh uninterrupted generation. Earlier versions are retained.

[Watch the final main video](https://youtu.be/vTliRuFi2HM). Full decoding, caption timing checks and nine sampled-frame visual checks passed: 1920×1080, 24 fps, 4,086 decoded frames and 37 English caption cues. Narration is synthetic. The app's fresh-generation evidence above is separate from the saved-report video.
