# Submission form answers (paste-ready)

**Team name:** Lineage

**Track:** Indie Developer

**Problem statement:** Push the Frontier

**Project description:**
Lineage is version control for a self-improving agent: every self-edit is a commit, the jury is CI, the review queue is a pull request, blame is git blame, rollback is git revert, and the locked test is the release gate. Concretely, it is an issue-triage agent that learns a real project's conventions from corrections, safely. It rewrites its own playbook, but no self-edit survives without passing a jury of Meta models on held-out data and a set of canary cases, a locked test set is scored once at the end and never used for gating, every decision can be traced to the rule and the edit that caused it, and any edit can be rolled back. It demonstrates on 1,269 real kubernetes/kubernetes issues with the project's own labels as ground truth. Across two full runs (seven lineages each), the gate rejected every edit learned from a deliberately relabeled batch (6 of 6) while every unsupervised agent absorbed it; one unsupervised agent fell from 66% to 55% on the locked test the generation it learned the lie (found with "lineage bisect"); unsupervised self-editing made sibling agents 41% different from each other on identical data (23% with the gate, 4% noise floor); and no lineage, gated or not, beat the frozen baseline on data it never saw. A positive-control run with a learnable convention was inconclusive and is reported as such. Live dashboard: https://romaisafatima1.github.io/lineage/dashboard/?run=../runs/full2/events.jsonl Lineage is the harness that tells you the truth about a self-improving agent: what it learned, whether it is real, and how to undo it. Dashboard with triage view, curves, divergence, edit diffs, review queue, blame with rule accountability, rollback, bisect and a cost meter; the harness also writes a one-page audit report per run.

**Public GitHub repository:** https://github.com/Romaisafatima1/lineage

**3-minute demo video:** (YouTube unlisted link)

**Describe your use of Meta products:**
Muse Spark (muse-spark-1.3) is the learning agent and juror 1: it triages issues at low reasoning effort, proposes structured playbook edits at medium effort, and scores edited playbooks on validation and canary cases. Muse Spark Open is juror 2 via an OpenAI-compatible host (Fireworks in the smoke runs; the full runs fell back to a second separately prompted Muse Spark call after Fireworks suspended the account over an uncleared credit purchase, which is logged and disclosed in the README). Muse Wonder (muse-wonder-1.0) is the arbiter: when the two jurors split, it rules at high reasoning and the item goes to a human review queue. Muse Code was used during the build. Prompt caching and JSON output mode are used on Model API; reasoning effort is dialed per role.

**Why are Meta's models important to your solution?**
The gate needs two things Meta's lineup gives together: a strong hosted model to be the agent and to score edits on known answers, and an open-weights model that a team could self-host so the audit trail never depends on a third party. Muse Wonder's adjustable reasoning lets the expensive thinking run only on the few verdicts that need it. A 1M-token context lets the whole lineage history ride along for blame.

**Feedback on partner technologies:**
Fireworks served Muse Spark Open well in testing (sub-3s responses) but a prepaid-credit purchase on a debit card never cleared and the account was suspended mid-event; the dashboard showed "Issued" with no balance and no clear next step. Baseten returned 404 for meta-models/muse-spark-open-1026 on a new account. Clearer billing states and an error message naming the model would have saved hours.

**Biggest obstacle:** Reasoning tokens silently consuming the output budget (empty replies), and provider billing failures during the final day. Both now handled: automatic retry with a bigger budget, and a logged fallback for juror 2.

**Compared with other models:** Muse Spark's triage was stable (4% self-disagreement at temperature 0 across three passes on 100 issues), which is what made a measured gate possible. Edit proposals were sometimes verbose; a word limit in the prompt fixed it.

**What matters most when choosing a model:** Determinism and structured-output reliability, because a verification gate is only as good as the repeatability of its measurements.

**Hardest thing about switching:** Prompt behavior around reasoning budgets and JSON mode differs per model; the rest is one base URL.

**What would stop production use:** Billing and quota reliability on the open-weights hosting side, and cost: the gate roughly triples per-generation spend versus unsupervised learning, which is the price of trust and is shown on the cost meter.

**Most Viral:** (X post link)
