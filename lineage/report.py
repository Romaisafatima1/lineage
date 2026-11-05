"""Write the one-page audit report a team lead would read on Monday.

    python -m lineage.report --run full2        # -> runs/full2/REPORT.md

Everything in it is computed from the event log.
"""

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from .run import EventLog


def pct(x):
    return f"{100 * x:.0f}%"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    a = p.parse_args()
    d = Path("runs") / a.run
    ev = EventLog.read(d / "events.jsonl")
    start = next(e for e in ev if e["type"] == "run_start")
    cfg = start["config"]
    lns = [l for l, _ in start["lineages"]]
    edits = [e for e in ev if e["type"] == "edit"]
    finals = {e["lineage"]: e for e in ev if e["type"] == "final_test"}
    states = {e["lineage"]: e for e in ev if e["type"] == "state"}
    cost = [e for e in ev if e["type"] == "cost"][-1] if any(e["type"] == "cost" for e in ev) else None
    div = [e for e in ev if e["type"] == "divergence"]
    probes = defaultdict(dict)
    for e in ev:
        if e["type"] == "probe":
            probes[e["lineage"]][e["gen"]] = e["score"]["both_acc"]
    rollbacks = [e for e in ev if e["type"] == "rollback"]
    rejudges = [e for e in ev if e["type"] == "rejudge"]
    base = finals.get("baseline", {}).get("score", {}).get("both_acc")

    out = []
    out.append(f"# Lineage audit report · run `{a.run}`\n")
    out.append(f"{cfg['gens']} generations · {len(lns)} lineages · batch {cfg['batch']} · validation {cfg['val']} · "
               f"locked test {cfg['test_n']} · repo {cfg['repo']}"
               + (f" · convention `{cfg['convention']}`" if cfg.get("convention") else "") + "\n")
    if cost:
        t = cost["total"]
        out.append(f"**Spend:** ${t['usd']:.2f} over {t['calls']} calls. Juror agreement: "
                   f"{cost['jury_agreement']['agree']} agreed, {cost['jury_agreement']['split']} split.\n")

    out.append("## Locked test (scored once, never used for gating)\n")
    out.append("| Lineage | Mode | Both labels | Kind | Area | Edits applied | Rules | vs baseline |")
    out.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for ln in lns:
        f = finals.get(ln)
        s = states.get(ln, {})
        if not f:
            continue
        sc = f["score"]
        delta = "" if base is None or ln == "baseline" else f"{100 * (sc['both_acc'] - base):+.0f} pts"
        out.append(f"| {ln} | {f['mode']} | **{pct(sc['both_acc'])}** | {pct(sc['kind_acc'])} | {pct(sc['area_acc'])} | "
                   f"{s.get('edits_applied', 0)} of {s.get('edits_proposed', 0)} | {len(f['playbook']['rules'])} | {delta} |")

    if div:
        last = div[-1]
        out.append("\n## Divergence (how differently sibling lineages behave on the same 50 probes)\n")
        out.append(f"At generation {last['gen']}: gated lineages **{pct(last['gated_mean'])}** apart, "
                   f"ungated **{pct(last['ungated_mean'])}** apart.")
        out.append("\n| Gen | " + " | ".join(lns) + " |")
        out.append("| --- |" + " --- |" * len(lns))
        for g in sorted({g for v in probes.values() for g in v}):
            out.append(f"| {g} | " + " | ".join(pct(probes[l][g]) if g in probes[l] else "" for l in lns) + " |")

    out.append("\n## What the agents tried to learn\n")
    dec = Counter((e["mode"], e["decision"]) for e in edits)
    out.append("| Mode | accept | reject | review | invalid |")
    out.append("| --- | --- | --- | --- | --- |")
    for mode in ("gated", "ungated"):
        out.append(f"| {mode} | {dec[(mode, 'accept')]} | {dec[(mode, 'reject')]} | {dec[(mode, 'review')]} | {dec[(mode, 'invalid')]} |")
    reasons = Counter(e["reason"].split(":")[0] for e in edits if e["mode"] == "gated" and e["decision"] == "reject")
    if reasons:
        out.append("\nWhy gated edits were rejected: " + "; ".join(f"{k} ({v})" for k, v in reasons.most_common()) + ".")

    poisoned = [e for e in edits if e.get("poisoned_batch")]
    if poisoned:
        out.append(f"\n## The adversarial test (generation {poisoned[0]['gen']})\n")
        out.append("Every real bug in that generation's learning batch was relabeled as a feature. "
                   "What each lineage proposed to learn from it, and what happened:\n")
        for e in poisoned:
            verdict = {"accept": "APPLIED", "reject": "REJECTED", "review": "SENT TO REVIEW", "invalid": "INVALID"}[e["decision"]]
            out.append(f"- **{e['lineage']}** ({e['mode']}): {verdict} — {e['reason']}  \n  > {e['edit'].get('text', '')[:220]}")

    accepted = [e for e in edits if e["mode"] == "gated" and e.get("applied")]
    if accepted:
        out.append("\n## Rules the gate let through\n")
        for e in accepted:
            sc = e.get("scores", {})
            s = " · ".join(f"{j.replace('juror_', '')} {pct(v['old'])}→{pct(v['new'])}" for j, v in sc.items())
            out.append(f"- **{e['lineage']}** g{e['gen']} `{e['edit']['op']}`: {e['edit'].get('text', '')[:200]}  \n  _{e['reason']}_ ({s})")

    out.append("\n## Rule accountability (which rules drove the misses)\n")
    out.append("For each lineage, the rules most often relied on in wrong locked-test decisions, with the edit that introduced them. "
               "Seed rules have no edit.\n")
    edit_by_id = {e["edit_id"]: e for e in edits}
    for ln in lns:
        f = finals.get(ln)
        if not f or ln == "baseline":
            continue
        rules = {r["id"]: r for r in f["playbook"]["rules"]}
        cited, wrong = Counter(), Counter()
        for x in f["decisions"]:
            ok = x["kind"] == x["true_kind"] and x["area"] in x["true_areas"]
            for rid in x.get("rule_ids", []):
                cited[rid] += 1
                if not ok:
                    wrong[rid] += 1
        rows = sorted(cited, key=lambda r: (-wrong[r], -cited[r]))[:3]
        if not rows:
            continue
        out.append(f"**{ln}**")
        for rid in rows:
            r = rules.get(rid)
            if not r:
                continue
            e = edit_by_id.get(r.get("edit_id")) if r.get("edit_id") else None
            origin = f"edit `{e['edit_id']}` g{e['gen']}, {e['decision']}" + (", poisoned batch" if e and e.get("poisoned_batch") else "") if e else "seed rule"
            out.append(f"- `{rid}` cited {cited[rid]}×, wrong {wrong[rid]}× ({pct(wrong[rid] / cited[rid])}) · {origin}  \n  > {r['text'][:160]}")
        out.append("")

    if rollbacks:
        out.append("\n## Rollbacks\n")
        for r in rollbacks:
            out.append(f"- **{r['lineage']}** without `{r['edit_id']}`: locked test {pct(r['with']['test']['both_acc'])} → "
                       f"{pct(r['without']['test']['both_acc'])}, validation {pct(r['with']['val']['both_acc'])} → {pct(r['without']['val']['both_acc'])}")
    if rejudges:
        out.append("\n## Re-judged with the full jury\n")
        for r in rejudges:
            out.append(f"- `{r['edit_id']}`: original {r['original_decision']}, full jury {r['decision']} ({r['reason']}); juror 2 = {r['juror2_model']}")

    out.append("\n## Reading this report\n")
    out.append("The locked test is the only number that counts; batch and probe accuracy are for watching the process. "
               "An edit the gate let through that later cost accuracy is a gate miss, and rollback is the remedy. "
               "Everything above is recomputed from `events.jsonl`; nothing is typed in by hand.")
    (d / "REPORT.md").write_text("\n".join(out) + "\n")
    print(f"wrote {d / 'REPORT.md'}")


if __name__ == "__main__":
    main()
