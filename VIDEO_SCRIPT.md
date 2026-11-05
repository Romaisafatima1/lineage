# Lineage — 3-minute demo script

Setup: dashboard open on `?run=../runs/full2/events.jsonl`, browser full screen, QuickTime screen recording with microphone. Speak slowly; 150 words a minute is plenty. Record in one take per section if easier, then trim. Say the words in **bold** exactly; everything else is a guide.

---

### 0:00–0:20 · The problem (Triage view, scroll slowly through the table)

**"I'm Romaisa. I triage bug reports and CI failures for a living. Teams want AI agents that learn from our corrections. Nobody ships one that rewrites its own instructions unsupervised, because it can learn the wrong lesson from one bad batch, and afterwards no one can say why it made a call. Lineage is version control for a self-improving agent: every self-edit is a commit, the jury is CI, blame is git blame, rollback is git revert."**

On screen: real kubernetes issues, the agent's label next to the project's label, the rules it relied on.

### 0:20–0:40 · How it works (stay on Triage; point at the playbook at the bottom)

**"The model never changes. The agent carries a playbook of rules, and after every batch of corrections it proposes one edit. The edit only survives if it passes a jury of Meta models on cases the agent never learns from, and breaks no canaries. A locked test set is scored once at the end and never used for gating. And every decision names the rule that caused it."**

### 0:40–1:05 · The adversarial test (Edits view, filter to `ungated-3`, open the g10 row)

**"At generation ten I injected the thing every maintainer has seen: a batch of real bugs relabeled as feature requests to shrink the bug count. The unsupervised agent learned this rule."** Read two lines of the rule aloud: *"even with reproduction steps, logs or stack trace, reports about missing API fields are features."* **"That rule is now permanently in its playbook."**

Switch the filter to `gated-3`, open its g10 row. **"The gated agent proposed the same lesson. The jury tested it on clean data, the canaries broke, and it was rejected. Six out of six poisoned edits were rejected across two runs; every unsupervised agent absorbed it."**

### 1:05–1:30 · Divergence (Divergence view)

**"Here is the finding I care most about. These lineages started from the same playbook and saw the same issues in the same order. Without the gate, they ended forty-one percent apart in how they triage. With it, twenty-three. The noise floor is four percent. Unsupervised self-editing produces different agents, not better ones."**

### 1:30–1:55 · Bisect and the locked test (Bisect view, then Curves bar chart)

**"Like git bisect, Lineage can score every historical playbook on data the agent never learned from. Here is the unsupervised agent: sixty-six percent at generation five, fifty-five the generation it learned the lie, and it never recovered. The gated agent on the same data: flat at the baseline the whole way."** Switch to Curves. **"And the honest number: on a hundred locked issues, nobody beat the frozen model. The batch curves look like learning. The locked test says otherwise. Most demos would have shown you the curves. Lineage shows you the test."**

### 1:55–2:25 · Blame and rollback (Blame view, pick a miss on `ungated-3`, then Rollback view)

**"When an agent gets something wrong, you want to know why. Blame traces this decision to the rule, the generation that added it, and the verdict that let it in — this one came from the poisoned batch."** Switch to Rollback. **"One command rebuilds the playbook without that edit and rescores it. It recovers two points, no more, because fifteen later edits were built on the bad lesson. Damage compounds. That is why Lineage gates before the change instead of cleaning up after."**

### 2:25–2:45 · Review queue and cost (Review queue, then Cost)

**"When the two jurors disagree, Muse Wonder rules at high reasoning and the item lands here for a human to approve or override."** Switch to Cost. **"The gate costs about three times what unsupervised learning costs. That's the price of trust, and it's on the meter."**

### 2:45–3:00 · Close (Cost view footer, or README on GitHub)

**"Muse Spark is the agent and first juror, Muse Spark Open the second, Muse Wonder the arbiter, built with Muse Code. The repo is public, every number comes from the event log, and the one place the gate missed is written in the README. Lineage: self-improvement you can audit."**

---

Tips: record the three screen sections first (0:40–2:45) since they carry the demo; do the intro and close last. If a view takes a second to render, pause, then cut it in editing. Keep it under 3:00 — judges may stop at the mark.
