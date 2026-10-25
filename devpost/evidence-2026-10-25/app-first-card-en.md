# Application comparison excerpt — English translation

Source: the recovered first paper card for arXiv 2610.31667v1. This translation is for review, not a new application language-generation test.

**Problem and idea:** Completing many candidate reasoning paths costs computation. Selecting only apparently reliable paths risks retaining similar paths that fail together; selecting only different paths may retain poor outliers. PKTP optimizes the probability that at least one retained path eventually answers correctly, accounting for dependence between candidate paths.

**Position:** Large-language-model reasoning efficiency → candidate pruning during test-time scaling → joint-distribution modeling and greedy selection under a pass@k objective.

**Result:** On DeepSeek-R1-Distill-Qwen-1.5B, at k=4, PKTP's pass@4 is 3.0 percentage points higher than Linear Probe and 3.2 points higher than RepExp [E0026]. The original excerpt on physical PDF page 11 was inspected separately, and the application's E0026 control opened that excerpt.

**Caveat:** At large k, PKTP approaches the diversity-only method; the paper suggests a weak correctness signal in partial-solution embeddings as a possible explanation.

This is a translated comparison excerpt, not a claim that the entire report was human-verified.
