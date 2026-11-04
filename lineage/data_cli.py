"""Download and inspect the issue dataset.

    python -m lineage.data_cli --repo kubernetes/kubernetes --pages 40
"""

import argparse
from collections import Counter

from .data import DATA_DIR, build_dataset, fetch_issues, load_issues


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default="kubernetes/kubernetes")
    p.add_argument("--pages", type=int, default=1, help="pages of 100 per (kind, sig) label pair")
    p.add_argument("--inspect", action="store_true", help="only summarise the cached file")
    args = p.parse_args()
    path = DATA_DIR / f"{args.repo.replace('/', '__')}.jsonl"
    issues = load_issues(path) if args.inspect else fetch_issues(args.repo, pages=args.pages, out=path)
    print(f"{len(issues)} qualifying issues")
    print("kinds:", Counter(i.kind for i in issues).most_common(10))
    print("areas:", Counter(a for i in issues for a in i.areas).most_common(12))
    try:
        ds = build_dataset(issues)
        print("dataset:", ds.summary())
    except ValueError as e:
        print("not enough yet:", e)


if __name__ == "__main__":
    main()
