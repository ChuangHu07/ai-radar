# English translation of the direct-chat baseline

This is an English translation of the preserved Chinese model output, prepared for review. It is not another model test. Page references and strong wording are retained rather than corrected; consult the evaluation report for the comparison's limits.

## 1. Research background and problem

In reasoning tasks for large language models, test-time scaling improves accuracy by generating many candidate solutions. However, running every candidate to completion consumes substantial computation. Researchers therefore use pruning: generate partial solutions, evaluate them, and continue only the most promising ones (pages 1–2).

Existing pruning methods fall into two groups. Quality-oriented methods, such as a linear probe, keep solutions predicted to be correct, but can select highly similar solutions that fail together. Diversity-oriented methods, such as RepExp, choose different reasoning trajectories to cover more possibilities, but may waste budget on poor outliers (page 3). The paper addresses this trade-off.

## 2. How PKTP works

The authors propose PKTP, Pass@k Thought Pruning. Instead of optimizing quality or diversity separately, it directly maximizes the retained set's pass@k: the probability that at least one solution is correct.

- **Probability model:** Even independently sampled solutions can have dependent outcomes. A latent Gaussian model represents their joint distribution, capturing the tendency of similar solutions to succeed or fail together (page 5).
- **Greedy algorithm:** Because exact optimization is NP-hard, the authors derive a closed-form second-order approximation and prove its submodularity, enabling efficient greedy subset selection (page 7).

## 3. Main findings

The authors experiment with eight open-weight reasoning models (page 9):

- **Performance:** PKTP outperforms the quality and diversity baselines in most cases.
- **Balance:** Its advantage is especially clear at moderate budgets, around k=4. Quality-only methods lack diversity, while diversity-only methods neglect quality; PKTP “perfectly balances” the two (page 11).
- **Robustness:** As the generation cutoff T increases, PKTP keeps improving, while other methods can fluctuate or decline (page 12).

## 4. Significance and limitations

**Significance:** The work exposes the exploration/exploitation tension in pruning and offers a theoretically supported, practically effective approach that substantially improves reasoning efficiency.

**Limitations:** At very large k, PKTP's advantage shrinks and its performance approaches RepExp. The paper suggests that correctness signals in early hidden representations may weaken as generation proceeds (page 11).

The original baseline is preserved in [baseline-zh.md](baseline-zh.md). This translation retains the baseline's “perfectly balances” wording for transparency; the evaluation does not endorse that universal claim.
