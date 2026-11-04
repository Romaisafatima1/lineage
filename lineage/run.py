"""
The runner: evolves a population of lineages and writes everything to an event log.

    python -m lineage.run --name demo --gated 3 --ungated 3 --baseline --gens 30
    python -m lineage.run --name smoke --mock --gated 1 --ungated 1 --gens 2

Lineage modes
- gated:    every proposed edit goes through the jury (validator -> jurors -> arbiter)
- ungated:  every valid edit is applied, no questions asked
- baseline: never edits; the frozen model with the seed playbook

All lineages see the same learning stream in the same order; differences come
only from what each one decided to learn. Every generation is synchronised
across lineages so probes and divergence are measured at the same points.

The event log (runs/<name>/events.jsonl) is the single source of truth: the
dashboard, blame, rollback and the final numbers are all computed from it, and
a run can resume from it after a crash.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import itertools
import json
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

from .agent import Playbook, propose_edit, score, triage
from .data import Dataset, Issue, build_dataset, load_issues, make_synthetic, DATA_DIR
from .jury import Jury, validate
from .llm import LLM, MockLLM


@dataclass
class Lineage:
    name: str
    mode: str                      # gated | ungated | baseline
    playbook: Playbook
    gen: int = 0
    usd: float = 0.0
    edits_proposed: int = 0
    edits_applied: int = 0


class EventLog:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.f = path.open("a")

    def write(self, ev: dict):
        ev["ts"] = round(time.time(), 3)
        self.f.write(json.dumps(ev) + "\n")
        self.f.flush()

    @staticmethod
    def read(path: Path) -> list[dict]:
        if not path.exists():
            return []
        with path.open() as f:
            return [json.loads(l) for l in f if l.strip()]


class Runner:
    def __init__(self, args, llm: LLM, ds: Dataset):
        self.args, self.llm, self.ds = args, llm, ds
        self.repo = args.repo
        self.dir = Path("runs") / args.name
        self.log = EventLog(self.dir / "events.jsonl")
        self.rng = random.Random(args.seed)
        self.lineages: list[Lineage] = []
        self.jury: Jury | None = None

    # ---------- setup ----------

    def make_lineages(self):
        seed_pb = Playbook.seed(self.ds.kinds, self.ds.areas)
        for i in range(self.args.gated):
            self.lineages.append(Lineage(f"gated-{i+1}", "gated", copy.deepcopy(seed_pb)))
        for i in range(self.args.ungated):
            self.lineages.append(Lineage(f"ungated-{i+1}", "ungated", copy.deepcopy(seed_pb)))
        if self.args.baseline:
            self.lineages.append(Lineage("baseline", "baseline", copy.deepcopy(seed_pb)))

    def resume(self) -> bool:
        """Rebuild lineage state from the log so a crashed run continues where it stopped."""
        events = EventLog.read(self.dir / "events.jsonl")
        states = {e["lineage"]: e for e in events if e["type"] == "state"}
        if not states:
            return False
        for ln in self.lineages:
            s = states.get(ln.name)
            if s:
                ln.playbook = Playbook.from_dict(s["playbook"])
                ln.gen, ln.usd = s["gen"], s["usd"]
                ln.edits_proposed, ln.edits_applied = s["edits_proposed"], s["edits_applied"]
        return True

    async def pick_canaries(self) -> list[Issue]:
        """Canaries = validation cases the seed playbook already gets right.
        An edit that breaks them has made the agent forget something it knew."""
        seed_pb = Playbook.seed(self.ds.kinds, self.ds.areas)
        decisions, usd = await triage(self.llm, "juror_spark", self.ds.val, seed_pb,
                                      self.ds.kinds, self.ds.areas, self.repo)
        right = [i for i, d in zip(self.ds.val, decisions)
                 if d["kind"] == d["true_kind"] and d["area"] in d["true_areas"]]
        self.rng.shuffle(right)
        canaries = right[: self.args.canaries]
        self.log.write({"type": "canaries", "ids": [c.id for c in canaries],
                        "seed_val_score": score(decisions), "usd": usd})
        return canaries

    # ---------- one generation of one lineage ----------

    def batch_for(self, gen: int) -> list[Issue]:
        n = self.args.batch
        start = ((gen - 1) * n) % len(self.ds.learn)
        batch = self.ds.learn[start:start + n]
        if len(batch) < n:
            batch += self.ds.learn[: n - len(batch)]
        return batch

    def poison(self, batch: list[Issue], gen: int) -> tuple[list[Issue], int]:
        """The declared adversarial test: at --poison-gen, every real bug in the
        batch is relabeled as a feature, the way a rushed maintainer closes out a
        bug count. The agent learns from the corrupted labels; the jury's
        validation set stays clean."""
        if gen != self.args.poison_gen:
            return batch, 0
        out, n = [], 0
        for i in batch:
            if i.kind == "bug" and "feature" in self.ds.kinds:
                j = copy.copy(i)
                j.kind = "feature"
                out.append(j)
                n += 1
            else:
                out.append(i)
        return out, n

    async def step(self, ln: Lineage, gen: int):
        t0 = time.time()
        batch = self.batch_for(gen)
        batch, poisoned = self.poison(batch, gen) if ln.mode != "baseline" else (batch, 0)
        decisions, usd = await triage(self.llm, "agent", batch, ln.playbook,
                                      self.ds.kinds, self.ds.areas, self.repo)
        ln.usd += usd
        gen_score = score(decisions)
        self.log.write({"type": "generation", "lineage": ln.name, "mode": ln.mode, "gen": gen,
                        "score": gen_score, "decisions": decisions, "poisoned": poisoned,
                        "playbook_hash": _h(ln.playbook), "usd": round(usd, 5)})
        if ln.mode == "baseline":
            ln.gen = gen
            self._state(ln)
            print(f"  {ln.name:11} g{gen:02d} acc={gen_score['both_acc']:.2f}")
            return

        edit, usd = await propose_edit(self.llm, decisions, batch, ln.playbook)
        ln.usd += usd
        ln.edits_proposed += 1
        edit_id = f"{ln.name}-g{gen}"
        ok, why = validate(edit, ln.playbook)
        ev = {"type": "edit", "lineage": ln.name, "mode": ln.mode, "gen": gen, "edit_id": edit_id,
              "edit": edit, "valid": ok, "validator_reason": why, "poisoned_batch": poisoned > 0,
              "before": ln.playbook.to_dict(), "usd": round(usd, 5)}
        if not ok:
            ev.update(applied=False, decision="invalid", reason=why)
            self.log.write(ev)
        else:
            new_pb = ln.playbook.apply(edit, gen, edit_id)
            if ln.mode == "ungated":
                ln.playbook = new_pb
                ln.edits_applied += 1
                ev.update(applied=True, decision="accept", reason="ungated: applied without review",
                          after=new_pb.to_dict())
            else:
                v = await self.jury.judge(ln.playbook, new_pb, edit)
                ln.usd += v.usd
                ev["usd"] = round(ev["usd"] + v.usd, 5)
                ev.update(decision=v.decision, reason=v.reason, votes=v.votes, scores=v.scores,
                          canary=v.canary, arbiter=v.arbiter)
                # 'review' = jurors split. Unattended runs follow the arbiter's ruling and
                # leave the item in the queue; a human can override it from the dashboard.
                apply = v.decision == "accept" or (v.decision == "review" and v.arbiter
                                                   and v.arbiter["decision"] == "accept")
                ev["applied"] = apply
                if apply:
                    ln.playbook = new_pb
                    ln.edits_applied += 1
                    ev["after"] = new_pb.to_dict()
            self.log.write(ev)
        ln.gen = gen
        self._state(ln)
        print(f"  {ln.name:11} g{gen:02d} acc={gen_score['both_acc']:.2f} {self._fmt(ev)} "
              f"{time.time() - t0:4.0f}s ${ln.usd:.2f}")

    def _fmt(self, ev: dict) -> str:
        if ev["type"] != "edit":
            return ""
        return f"{ev['edit'].get('op', '?'):6} -> {ev['decision']:7} {ev['reason'][:50]}"

    def _state(self, ln: Lineage):
        self.log.write({"type": "state", "lineage": ln.name, "mode": ln.mode, "gen": ln.gen,
                        "playbook": ln.playbook.to_dict(), "usd": round(ln.usd, 4),
                        "edits_proposed": ln.edits_proposed, "edits_applied": ln.edits_applied})

    # ---------- probes, divergence, final test ----------

    async def probe(self, gen: int):
        async def one(ln: Lineage):
            d, usd = await triage(self.llm, "agent", self.ds.probe, ln.playbook,
                                  self.ds.kinds, self.ds.areas, self.repo)
            ln.usd += usd
            return ln.name, d
        results = dict(await asyncio.gather(*(one(ln) for ln in self.lineages)))
        labels = {name: [(x["kind"], x["area"]) for x in d] for name, d in results.items()}
        for name, d in results.items():
            self.log.write({"type": "probe", "lineage": name, "gen": gen, "score": score(d),
                            "labels": labels[name]})
        pair = {}
        for a, b in itertools.combinations(labels, 2):
            dis = sum(x != y for x, y in zip(labels[a], labels[b])) / max(len(labels[a]), 1)
            pair[f"{a}|{b}"] = round(dis, 4)

        def mean(keys):
            v = [pair[k] for k in keys]
            return round(sum(v) / len(v), 4) if v else None
        gated = [k for k in pair if k.split("|")[0].startswith("gated") and k.split("|")[1].startswith("gated")]
        ungated = [k for k in pair if k.split("|")[0].startswith("ungated") and k.split("|")[1].startswith("ungated")]
        self.log.write({"type": "divergence", "gen": gen, "pairwise": pair,
                        "gated_mean": mean(gated), "ungated_mean": mean(ungated)})
        print(f"  divergence g{gen}: gated={mean(gated)} ungated={mean(ungated)}")

    async def final_test(self):
        """Scored once, on the locked test set, never used for gating. The headline."""
        async def one(ln: Lineage):
            d, usd = await triage(self.llm, "agent", self.ds.test, ln.playbook,
                                  self.ds.kinds, self.ds.areas, self.repo)
            ln.usd += usd
            return ln, d
        for ln, d in await asyncio.gather(*(one(ln) for ln in self.lineages)):
            s = score(d)
            self.log.write({"type": "final_test", "lineage": ln.name, "mode": ln.mode, "score": s,
                            "decisions": d, "playbook": ln.playbook.to_dict(), "usd": round(ln.usd, 4)})
            print(f"  FINAL {ln.name:11} both={s['both_acc']:.3f} kind={s['kind_acc']:.3f} "
                  f"area={s['area_acc']:.3f}  ${ln.usd:.2f}")

    # ---------- main loop ----------

    async def run(self):
        self.make_lineages()
        resumed = self.resume()
        self.log.write({"type": "run_start", "config": vars(self.args), "dataset": self.ds.summary(),
                        "resumed": resumed, "lineages": [(l.name, l.mode) for l in self.lineages]})
        canaries = await self.pick_canaries()
        self.jury = Jury(self.llm, self.ds.val, canaries, self.ds.kinds, self.ds.areas, self.repo)
        start = min(l.gen for l in self.lineages) + 1
        if resumed:
            print(f"resuming from generation {start}")
        for gen in range(start, self.args.gens + 1):
            print(f"generation {gen}/{self.args.gens}")
            await asyncio.gather(*(self.step(ln, gen) for ln in self.lineages if ln.gen < gen))
            if gen % self.args.probe_every == 0 or gen == self.args.gens:
                await self.probe(gen)
            self.log.write({"type": "cost", "gen": gen, "total": self.llm.usage.snapshot(),
                            "by_model": self.llm.usage.by_model,
                            "jury_agreement": self.jury.agreements,
                            "per_lineage": {l.name: round(l.usd, 4) for l in self.lineages}})
        if not self.args.no_final:
            await self.final_test()
        self.log.write({"type": "run_end", "total": self.llm.usage.snapshot()})
        print(f"done. total ${self.llm.usage.usd:.2f}, {self.llm.usage.calls} calls. "
              f"log: {self.dir / 'events.jsonl'}")


def _h(pb: Playbook) -> str:
    from .jury import pb_hash
    return pb_hash(pb)


def load_dataset(args) -> Dataset:
    if args.mock:
        return build_dataset(make_synthetic(), val_n=20, probe_n=20, test_n=30, min_per_label=5)
    path = DATA_DIR / f"{args.repo.replace('/', '__')}.jsonl"
    if not path.exists():
        raise SystemExit(f"no data at {path}. Run: python -m lineage.data_cli --repo {args.repo}")
    return build_dataset(load_issues(path), val_n=args.val, probe_n=args.probe_n, test_n=args.test_n)


def main():
    p = argparse.ArgumentParser(description="Evolve a population of triage agents.")
    p.add_argument("--name", required=True, help="run name; log goes to runs/<name>/events.jsonl")
    p.add_argument("--repo", default="kubernetes/kubernetes")
    p.add_argument("--gated", type=int, default=3)
    p.add_argument("--ungated", type=int, default=3)
    p.add_argument("--baseline", action="store_true", default=True)
    p.add_argument("--no-baseline", dest="baseline", action="store_false")
    p.add_argument("--gens", type=int, default=30)
    p.add_argument("--batch", type=int, default=20, help="issues learned from per generation")
    p.add_argument("--val", type=int, default=40)
    p.add_argument("--canaries", type=int, default=15)
    p.add_argument("--probe-n", type=int, default=50)
    p.add_argument("--probe-every", type=int, default=5)
    p.add_argument("--test-n", type=int, default=100)
    p.add_argument("--poison-gen", type=int, default=12, help="0 disables the adversarial test")
    p.add_argument("--no-final", action="store_true")
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--spend-cap", type=float, default=200.0)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--mock", action="store_true", help="offline: fake model, synthetic data")
    args = p.parse_args()

    ds = load_dataset(args)
    llm = MockLLM() if args.mock else LLM(max_concurrency=args.concurrency, spend_cap_usd=args.spend_cap)
    print(f"dataset: {ds.summary()}")
    asyncio.run(Runner(args, llm, ds).run())


if __name__ == "__main__":
    main()
