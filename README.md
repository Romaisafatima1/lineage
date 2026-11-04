# Lineage

**An issue-triage agent that learns a real project's conventions from corrections, safely.**

Built solo during the Meta Global AI Developer Hackathon, Oct 26 – Nov 4, 2026 (repo started Nov 3). Indie Developer track, *Push the Frontier*.

Teams want agents that learn from their mistakes. Nobody ships one that rewrites its own instructions unsupervised, because it can learn the wrong lesson from one bad batch, quietly forget what it did well, and nobody can say afterwards why it made a call. Lineage removes that trade-off: the agent improves itself, and every change is **tested before it is kept, traceable afterwards, and reversible**.

It demonstrates on a job every software team does: triaging issues in [kubernetes/kubernetes](https://github.com/kubernetes/kubernetes), deciding each issue's *kind* (bug, feature, cleanup, ...) and the owning *area* (sig), with the project's real labels as ground truth.

## How it works

The model never changes. The agent carries a written playbook of rules and, after each batch of corrections, proposes **one structured edit** (add / change / delete a rule). The edit survives only if it passes the gate:

1. **Validator** (code, free) — drops malformed, duplicate or single-issue rules.
2. **Jury** (Muse Spark + Muse Spark Open) — runs the *edited* playbook on validation cases the agent never learns from, plus fixed **canary** cases it already gets right. Keep only if it helps on new cases and breaks nothing old. The gate is empirical: edits are judged on known answers, not on a model's opinion.
3. **Arbiter** (Muse Wonder) — only when the jurors split; rules at high reasoning, and the item goes to a **human review queue** where a person can override.

A **population** of lineages evolves in parallel from the same seed playbook on the same data: gated lineages, ungated lineages that apply every edit, and a frozen baseline that never learns. A fixed probe set measures how far lineages drift apart. A **locked test set** is scored once at the end and never used for gating; that number is the headline.

Every decision records the rules it relied on, and every rule records the edit and generation that created it, so any wrong call can be **blamed** on the edit that caused it and **rolled back**.

## Meta models, each with one job

| Model | Where | Job |
| --- | --- | --- |
| Muse Spark `muse-spark-1.3` | Meta Model API | The learning agent; juror 1 |
| Muse Spark Open | Fireworks serverless | Juror 2: a different deployment a team could self-host for audit |
| Muse Wonder `muse-wonder-1.0` | Meta Model API | Arbiter on split verdicts |
| Muse Code | — | Used during the build |

Built with Muse Spark Open.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # add META_API_KEY and FIREWORKS_API_KEY

python -m lineage.data_cli --pages 40                 # ~1,500 labeled kubernetes issues, no token needed
python -m lineage.run --name smoke --mock --gens 3    # offline check, costs nothing
python -m lineage.run --name demo --gated 3 --ungated 3 --gens 30 --poison-gen 12
```

Every run writes `runs/<name>/events.jsonl`. The dashboard, blame, rollback and the final numbers are all computed from that log, and a crashed run resumes from it with the same command.

## The adversarial test

At `--poison-gen`, every real bug in that generation's batch is relabeled as a feature, the way a rushed maintainer closes out a bug count. The agent learns from the corrupted labels; the jury's validation set stays clean. Ungated lineages absorb the bad rule; gated lineages reject it. This is a declared chaos test, not a hidden one.

## Prior work

Agents that improve by editing their own context are an active research line (e.g. agentic context engineering). Lineage does not claim that idea. Its contribution is the layer those systems need before a team would trust them: verification before change, honest evaluation on locked data, and accountability (blame, rollback) after change.

## Next jobs for the same harness

CI test-failure triage (real bug / flaky / environment), PR review, and test-maintenance agents all fit the same loop: a playbook, corrections with ground truth, and a gate.

## Tests

```bash
python -m unittest discover -s tests
```

MIT licensed. See `LICENSE`.
