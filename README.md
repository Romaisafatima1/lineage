# Lineage

**Version control for a self-improving agent: every self-edit is a commit, the jury is CI, the review queue is a pull request, blame is `git blame`, rollback is `git revert`, and the locked test is the release gate.**

An issue-triage agent that learns a real project's conventions from corrections, where nothing it learns is kept until it passes a jury on data it never trained on, every decision can be traced to the rule and the edit that caused it, and any edit can be bisected and reverted.

Built solo in two days during the Meta Global AI Developer Hackathon (repo started Nov 3, 2026). Indie Developer track · *Push the Frontier*.

**[Live dashboard on the real run](https://romaisafatima1.github.io/lineage/dashboard/?run=../runs/full2/events.jsonl)** · [Audit report the harness wrote](runs/full2/REPORT.md) · [Run log](runs/full2/events.jsonl) · [Tests](.github/workflows/tests.yml)

> Most "self-improving agent" demos show batch accuracy going up and call it learning. Lineage puts a locked test set, canaries and a jury between the agent and its own edits, and then reports what it found. On 1,269 real kubernetes issues, across two full runs: **the gate rejected every edit learned from a poisoned batch (6 of 6) while every unsupervised agent absorbed it; one unsupervised agent's accuracy on unseen data fell from 66% to 55% the generation it learned the lie, and never recovered; unsupervised self-editing made sibling agents 41% different from each other on identical data (23% with the gate, 4% noise floor); and nobody, gated or not, beat the frozen model on data it never saw.** The agent could not fool the harness. The harness tells you the truth.

![lineage bisect](docs/bisect.png)

## Why this matters

Every engineering team is about to run agents that act on their behalf: triaging issues, routing failures, answering support, reviewing code. The obvious next step is letting those agents learn from the corrections people make every day. The obvious danger is that an agent which rewrites its own instructions can learn the wrong lesson from one bad batch, quietly forget what it did well, and leave nobody able to say why it made a call. Published work agrees: self-editing context systems *degrade without reliable feedback* (ACE, ICLR 2026), and planted "experiences" persist and get imitated (MemoryGraft, Bad Memory). Sakana's Darwin Gödel Machine was caught faking a test log, and only because its lineage was traceable.

So teams keep their agents frozen, and frozen agents stay mediocre. Lineage removes that trade-off. It is the missing layer between "the agent proposed a change to itself" and "the change is live": verification before, accountability after, and an honest number at the end. It applies to any job with corrections and ground truth, and it needs no fine-tuning, no ML team and no GPU: the model never changes, only a readable playbook does.

## Practical significance: how a team uses it

1. **Point it at the tracker.** New issues get a proposed kind and owning team, with the rules the agent relied on shown next to each call. A triager accepts or corrects in one click.
2. **Corrections become edits, not retraining.** Each day's corrections produce one proposed playbook change, in plain English, as a diff.
3. **The gate runs overnight.** The edited playbook is scored on held-out cases and on canaries (things the agent already gets right). Split verdicts go to a review queue a lead clears on Monday in minutes; Muse Wonder's ruling is attached.
4. **When someone complains, blame answers.** "Why did it send my crash report to the wrong team?" is one click to the rule, the edit, the generation and the verdict that let it in. Rule accountability ranks the rules behind the most misses.
5. **When a bad batch slips in, bisect finds it and rollback undoes it.** A relabeling spree or a mislabeled import never becomes permanent behaviour.
6. **The locked test keeps everyone honest.** A held-back set, scored once, says whether the agent is better than it was, not just different.

The same loop fits CI failure triage (bug / flaky / environment), support routing, PR review and test maintenance.

## How it works

The model never changes. The agent (Muse Spark) carries a playbook of rules and, after each batch of 20 corrections, proposes **one structured edit** (add / change / delete a rule) with a reason. The edit survives only if it passes:

1. **Validator** (code, free): malformed, duplicate or single-issue rules are dropped.
2. **Jury** (two model calls, Muse Spark and the open-weights juror): the *edited* playbook is run on a validation set the agent never learns from, and on canaries. Keep only if validation improves and no more than two canaries break. The gate is empirical: edits are judged on known answers, not on a model's opinion of the edit.
3. **Arbiter** (Muse Wonder): when the jurors split, Wonder rules at high reasoning and the item goes to a human review queue.

A **population** evolves in parallel from the same seed playbook on the same issues in the same order: 3 gated lineages, 3 ungated lineages that apply every edit, and a frozen baseline. A fixed 50-issue probe set measures how far lineages drift apart. A **locked test set** of 100 issues is scored once at the end and never used for gating. Every decision names the rules it relied on; every rule records the edit and generation that created it.

Tools over the event log: `report` (one-page audit), `diag` (probe table, poisoned edits, noise floor), `rollback` (rebuild without an edit and rescore), `bisect` (score each historical playbook), `rejudge` (re-run the jury on an edit). The dashboard has eight views: Triage, Curves, Divergence, Edits (diffs with verdicts), Review queue, Blame (with rule accountability), Rollback, Bisect, Cost.

## Results

Run 2: 25 generations, 7 lineages, 3,480 model calls, $31. Run 1 (30 generations, validation 40) replicates the pattern. Data: 1,269 closed kubernetes/kubernetes issues with the project's own `kind/` and `sig/` labels as ground truth, no synthetic data.

### The evaluation ladder

| Test | Question | Result |
| --- | --- | --- |
| **Negative control** (poisoned batch, gen 10) | Does the gate block a bad lesson? | **Blocked 6 of 6** across two runs; every ungated agent absorbed it. ungated-3 fell 66% → 55% on the locked test the generation it learned the lie (bisect), and its probe accuracy halved, 50% → 26%, five generations later |
| **Real labels, no intervention** | Does self-editing beat a frozen model? | **No lineage did**, in either run. ungated-3 made 25 edits and finished 7 points below the baseline. The batch curves look like learning; the locked test says otherwise |
| **Positive control** (a team-name convention, two seeds) | Does the gate let a real rule through? | The gate accepted 3–4 rules per run; lineages finished 0 to +6 points over baseline, near the 4% noise floor. **Inconclusive**: the frozen model inferred the convention from the name. A harder convention is the next experiment |

### Locked test, run 2

| | Gated (3) | Ungated (3) | Frozen baseline |
| --- | --- | --- | --- |
| Poisoned edit (gen 10) | **rejected 3 / 3** | applied 3 / 3 | — |
| Divergence between lineages at gen 25 | **23%** | 41% | (noise floor 4%) |
| Locked test, both labels right | 62 / 61 / 67% | 67 / 64 / 55% | 62% |
| Edits applied of 25 proposed | 1–3 | 25 | 0 |

![locked test](docs/locked_test.png)

**The adversarial test.** At generation 10, every real bug in that batch is relabeled as a feature, the way a rushed maintainer closes out a bug count. It is a declared chaos test, and it simulates the memory-poisoning threat in the literature. The ungated agents learned rules like *"A report of incorrect or missing behavior that can only be fixed by new validation is feature, not bug, even with repro/logs."* The gated agents proposed the same lesson and the jury rejected it every time: on validation score in run 2, on canaries in run 1.

![probes](docs/probes.png)

**Divergence is real.** The noise floor, measured by scoring the same playbook on the same 100 issues three times, is 4%. Descendants of one agent on identical data ended 41% apart without the gate and 23% with it. Self-editing without verification produces different agents, not better ones.

![divergence](docs/divergence.png)

**Nobody beat the baseline, and the harness said so.** Rolling back ungated-3's poisoned edit after the fact recovered only 2 points (58% → 60%): fifteen later edits had compounded on it. Prevention beats rollback.

**One gate miss, owned.** In run 1, gated-1 accepted a single edit that passed 40 validation cases but cost it about 14 points on the probe set. Run 2 raised validation to 60. The limitation is stated here rather than hidden.

The full audit reports the harness wrote: [run 2](runs/full2/REPORT.md) · [run 1](runs/full/REPORT.md) · [control](runs/control/REPORT.md) · [control, seed 2](runs/control2/REPORT.md).

## Meta models, each with one job

| Model | Where | Job |
| --- | --- | --- |
| Muse Spark `muse-spark-1.3` | Meta Model API | The learning agent; juror 1. Low reasoning for triage, medium for proposing edits; JSON mode; prompt caching |
| Muse Spark Open | Fireworks / Baseten (`JUROR2_*` env) | Juror 2: a different deployment a team could self-host for audit |
| Muse Wonder `muse-wonder-1.0` | Meta Model API | Arbiter on split verdicts, high reasoning |
| Muse Code | — | Used during the build |

**Disclosure.** The open-weights juror ran on Fireworks in the Nov 3 smoke runs. During the Nov 4 full runs Fireworks suspended the account over a prepaid-credit purchase that never cleared, and Baseten returned 404 for the model, so juror 2 fell back to a second, separately prompted Muse Spark call. The fallback is logged in every run (`!! juror-2 provider error`), the code path is unchanged, and `lineage.rejudge` re-runs any edit through the full jury once a host is available. Built with Muse Spark Open.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                                  # META_API_KEY, FIREWORKS_API_KEY or JUROR2_*

python -m lineage.data_cli                            # ~1,300 labeled kubernetes issues, no token needed
python -m lineage.run --name smoke --mock --gens 3    # offline, costs nothing, no keys
python -m lineage.run --name demo --gated 3 --ungated 3 --gens 25 --val 60 --poison-gen 10

python -m http.server 8000                            # open /dashboard/?run=../runs/demo/events.jsonl
python -m lineage.report --run demo                   # runs/demo/REPORT.md
python -m lineage.diag --run demo                     # probe table, poisoned edits, noise floor
python -m lineage.bisect --run demo --lineage ungated-3
python -m lineage.rollback --run demo --lineage ungated-3 --edit ungated-3-g10
python -m lineage.rejudge --run demo --edits gated-1-g10
python -m lineage.run --name control --convention platform --gens 12   # positive control
```

Every run writes `runs/<name>/events.jsonl`. The dashboard, blame, rollback, bisect, the report and every number above are computed from that log, and a crashed run resumes from it with the same command. Tests run on every push ([GitHub Actions](.github/workflows/tests.yml)), including an offline end-to-end run with a mock model.

## Prior work and what is new

Agents that improve by editing their own context are an active research line: [ACE](https://arxiv.org/abs/2510.04618) treats context as an itemized playbook of deltas and reports that such systems degrade without reliable feedback, naming "context collapse" as a failure mode; [Dynamic Cheatsheet](https://arxiv.org/abs/2504.07952) and [GEPA](https://arxiv.org/abs/2507.19457) evolve prompts and strategies from execution feedback; Sakana's [Darwin Gödel Machine](https://sakana.ai/dgm/) keeps an archive of every ancestor, which is how its authors caught it faking a test log. Memory-poisoning work ([MemoryGraft](https://arxiv.org/abs/2512.16962), [Bad Memory](https://huggingface.co/papers/2607.14611)) shows planted experiences persist and get imitated, which is the threat Lineage's adversarial test simulates.

Lineage does not claim the self-editing idea. Its contribution is the layer those systems need before a team would trust them: verification on held-out data before a change, canaries against forgetting, a locked test set so the headline number is one a reviewer can trust, and blame, bisect and rollback after a change. We found no prior hackathon project doing playbook version control with a jury gate; uncommon, not unprecedented.

## Future work

- **Falsifiable edit hypotheses.** Each proposed edit names the cases it will fix and the cases it must not change; the gate checks the prediction, and blame shows predicted versus actual. Edits become testable claims.
- **Jury stability score.** Re-score each verdict with shuffled case order and repeated passes; verdicts that flip become automatic splits (after the position-bias literature on LLM judges).
- **Lower-confidence-bound gating.** Accept on the LCB of the gain across jurors and passes, so noisy one-case wins cannot pass; this would have caught run 1's gate miss.
- **Pareto selection across lineages** (GEPA): keep any lineage that wins on at least one validation case and show the frontier, instead of promoting one winner.
- **A harder positive control** (a convention that cannot be inferred from a name), and the second domain the harness was designed for: CI test-failure triage.
- **Context-collapse guard:** reject any edit that shrinks the playbook by more than a set fraction.

## Repository

```
lineage/   llm.py (clients, cost, fallback, mock) · data.py (GitHub issues, splits) · agent.py (playbook, triage, propose)
           jury.py (validator, jury, arbiter) · run.py (population runner, event log, poisoning, convention)
           report.py · diag.py · rollback.py · bisect.py · rejudge.py
dashboard/ index.html (single file, Chart.js)        runs/ event logs and reports        tests/ offline tests
```

MIT licensed.
