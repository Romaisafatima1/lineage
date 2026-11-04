"""
Data for Lineage: real GitHub issues, with the project's own labels as ground truth.

Default repo is kubernetes/kubernetes because its labels are clean and
project-specific: every issue carries one `kind/*` label (bug, feature,
cleanup, ...) and one or more `sig/*` labels naming the owning team. A model
cannot guess kubernetes' conventions out of the box, so there is real room
for a playbook to learn them.

The loader works without a token (GitHub allows 60 unauthenticated requests
an hour, 100 issues each). Set GITHUB_TOKEN in .env to go faster.

Splits (fixed seed, so every lineage sees exactly the same data):
- learn:  the stream the agent learns from, in batches
- val:    what the jury scores proposed edits on; the agent never learns from it
- probe:  fixed set used to measure how far lineages drift apart
- test:   locked; scored once at the very end, never used for gating
"""

from __future__ import annotations

import json
import os
import random
import re
import time
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path

import urllib.error
import urllib.parse
import urllib.request

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(os.environ.get("LINEAGE_DATA_DIR", "data"))

# Issue templates add a lot of boilerplate; strip the common headers so the
# model sees the report, not the form.
_BOILERPLATE = re.compile(
    r"(<!--.*?-->|\*\*What happened\??\*\*|\*\*What you expected to happen\??\*\*|"
    r"\*\*How to reproduce it.*?\*\*|\*\*Anything else we need to know\??\*\*|"
    r"\*\*Kubernetes version\*\*|\*\*Cloud provider\*\*|\*\*OS version\*\*|"
    r"\*\*Install tools\*\*|\*\*Container runtime.*?\*\*|\*\*Related plugins.*?\*\*|"
    r"\*\*Environment\*\*:?|/kind \w+|/sig [\w-]+|/area [\w-]+|/triage \w+)",
    re.S | re.I,
)


@dataclass
class Issue:
    id: str
    title: str
    body: str
    kind: str
    areas: list          # owning sigs, 1 or 2; the agent is right if it names either
    url: str

    @property
    def area(self) -> str:
        return self.areas[0]

    def prompt_block(self, max_body: int = 900) -> str:
        body = self.body[:max_body].strip()
        return f"ISSUE {self.id}: {self.title}\n{body}\n"


def clean_body(text: str | None, limit: int = 1500) -> str:
    if not text:
        return ""
    text = _BOILERPLATE.sub(" ", text)
    text = re.sub(r"```.*?```", " [code] ", text, flags=re.S)
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()[:limit]


def parse_issue(raw: dict, kind_prefix="kind/", area_prefix="sig/") -> Issue | None:
    """Turn one GitHub API issue into an Issue, or None if it doesn't qualify.

    Qualifies = not a pull request, exactly one kind label, one or two area labels.
    Kubernetes bugs usually name two owning sigs, so allowing two keeps the bug
    class populated; the agent is scored right if it names either.
    """
    if "pull_request" in raw:
        return None
    labels = [l["name"] for l in raw.get("labels", [])]
    kinds = [l[len(kind_prefix):] for l in labels if l.startswith(kind_prefix)]
    areas = [l[len(area_prefix):] for l in labels if l.startswith(area_prefix)]
    if len(kinds) != 1 or not 1 <= len(areas) <= 2:
        return None
    title = (raw.get("title") or "").strip()
    if len(title) < 8:
        return None
    return Issue(id=str(raw["number"]), title=title, body=clean_body(raw.get("body")),
                 kind=kinds[0], areas=sorted(areas), url=raw.get("html_url", ""))


def _ssl_context():
    """python.org macOS builds ship without root certs; use certifi's bundle if present."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


# Label pairs to query. Asking GitHub for issues that carry BOTH labels gets
# on-target issues directly and keeps the classes balanced; scanning newest-first
# only yields ~5% usable issues and stops at page 10.
KINDS = ["bug", "feature", "cleanup", "support"]
SIGS = ["node", "network", "api-machinery", "scheduling", "storage", "auth", "apps", "cli"]


def _get(url: str, headers: dict, verbose: bool):
    while True:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60, context=_ssl_context()) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="ignore").lower()
            if e.code in (403, 429) and "rate limit" in body:
                reset = int(e.headers.get("x-ratelimit-reset", time.time() + 60))
                wait = max(5, reset - int(time.time()))
                if verbose:
                    print(f"rate limited; sleeping {wait}s (set GITHUB_TOKEN in .env to avoid this)")
                time.sleep(wait)
                continue
            if e.code == 422:          # pagination limit: nothing more on this query
                return []
            raise


PAGES_PER_KIND = {"bug": 4, "feature": 4, "cleanup": 2, "support": 1}


def fetch_issues(repo: str = "kubernetes/kubernetes", pages: int = 1,
                 out: Path | None = None, verbose: bool = True,
                 kinds: list[str] = KINDS, sigs: list[str] = SIGS) -> list[Issue]:
    """Download closed issues for every (kind, sig) label pair; keep those with
    exactly one kind and one sig label. `pages` = pages of 100 per pair."""
    out = out or DATA_DIR / f"{repo.replace('/', '__')}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "lineage-hackathon"}
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    seen: set[str] = set()
    issues: list[Issue] = []
    for kind in kinds:
        for sig in sigs:
            for page in range(1, max(pages, PAGES_PER_KIND.get(kind, 1)) + 1):
                q = urllib.parse.urlencode({"state": "closed", "per_page": 100, "page": page,
                                            "labels": f"kind/{kind},sig/{sig}",
                                            "sort": "created", "direction": "desc"})
                batch = _get(f"https://api.github.com/repos/{repo}/issues?{q}", headers, verbose)
                kept = []
                for raw in batch:
                    i = parse_issue(raw)
                    if i and i.id not in seen:
                        seen.add(i.id)
                        kept.append(i)
                issues.extend(kept)
                if verbose:
                    print(f"kind/{kind:8} sig/{sig:14} p{page}: {len(batch):3} items, kept {len(kept):3}, total {len(issues)}")
                if len(batch) < 100:
                    break
    with out.open("w") as f:
        for i in issues:
            f.write(json.dumps(asdict(i)) + "\n")
    if verbose:
        print(f"saved {len(issues)} issues to {out}")
    return issues


def load_issues(path: Path) -> list[Issue]:
    out = []
    with Path(path).open() as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                if "area" in d and "areas" not in d:      # older cache format
                    d["areas"] = [d.pop("area")]
                out.append(Issue(**d))
    return out


@dataclass
class Dataset:
    kinds: list[str]
    areas: list[str]
    learn: list[Issue]
    val: list[Issue]
    probe: list[Issue]
    test: list[Issue]

    def summary(self) -> dict:
        return {"kinds": self.kinds, "areas": self.areas,
                "learn": len(self.learn), "val": len(self.val),
                "probe": len(self.probe), "test": len(self.test)}


def build_dataset(issues: list[Issue], *, max_kinds: int = 5, max_areas: int = 8,
                  min_per_label: int = 25, val_n: int = 40, probe_n: int = 50,
                  test_n: int = 100, seed: int = 7) -> Dataset:
    """Keep the common labels, then split with a fixed seed.

    Restricting to the most common kinds and areas keeps the task learnable:
    a label with five examples can't be learned or scored fairly.
    """
    kc = Counter(i.kind for i in issues)
    ac = Counter(a for i in issues for a in i.areas)
    kinds = [k for k, n in kc.most_common(max_kinds) if n >= min_per_label]
    areas = [a for a, n in ac.most_common(max_areas) if n >= min_per_label]
    pool = [i for i in issues if i.kind in kinds and all(a in areas for a in i.areas)]
    rng = random.Random(seed)
    rng.shuffle(pool)
    if len(pool) < val_n + probe_n + test_n + 100:
        raise ValueError(f"only {len(pool)} usable issues; fetch more pages or lower the split sizes")
    test, pool = pool[:test_n], pool[test_n:]
    probe, pool = pool[:probe_n], pool[probe_n:]
    val, pool = pool[:val_n], pool[val_n:]
    return Dataset(kinds=kinds, areas=areas, learn=pool, val=val, probe=probe, test=test)


def make_synthetic(n: int = 600, seed: int = 3) -> list[Issue]:
    """Small fake corpus for offline tests and --mock runs. Not for the demo."""
    rng = random.Random(seed)
    areas = ["node", "network", "api-machinery", "scheduling", "storage", "auth"]
    kinds = ["bug", "feature", "cleanup", "support"]
    verbs = {"bug": ["crashes", "fails", "panics", "returns error", "is broken"],
             "feature": ["add support for", "allow", "add flag for", "support"],
             "cleanup": ["remove deprecated", "refactor", "tidy", "rename"],
             "support": ["how do I", "question about", "unclear docs for"]}
    nouns = {"node": ["kubelet", "cgroup", "pod eviction"], "network": ["kube-proxy", "service IP", "DNS"],
             "api-machinery": ["apiserver", "CRD", "watch cache"], "scheduling": ["scheduler", "affinity", "preemption"],
             "storage": ["PVC", "CSI driver", "volume mount"], "auth": ["RBAC", "token", "certificate"]}
    out = []
    for i in range(n):
        k, a = rng.choice(kinds), rng.choice(areas)
        title = f"{rng.choice(nouns[a])} {rng.choice(verbs[k])} when {rng.choice(['upgrading', 'scaling', 'restarting', 'under load'])}"
        out.append(Issue(id=str(100000 + i), title=title, body=f"Observed on cluster {rng.randint(1, 99)}.",
                         kind=k, areas=[a], url=""))
    return out
