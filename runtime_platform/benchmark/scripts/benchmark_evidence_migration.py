"""Read-only inventory and reconciliation of evidence refs between two stores (#690).

Contract: `runtime_platform/benchmark/scheduled-operations/private-evidence-cutover-runbook.md`.
Never pushes, deletes or rewrites a ref; it only fetches into a throwaway bare repository.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

EXIT_OK, EXIT_MISMATCH, EXIT_ERROR = 0, 1, 2
SCHEMA = "evidence-inventory/v1"


def _git(cwd: str, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed: {proc.stderr.strip().splitlines()[-1:]}")
    return proc.stdout


def in_scope(ref: str, namespaces: list[str], history_branch: str) -> bool:
    if ref == f"refs/heads/{history_branch}":
        return True
    return any(ref.startswith(f"refs/heads/{ns}") for ns in namespaces)


def inventory(remote: str, namespaces: list[str], history_branch: str) -> dict:
    """Every in-scope branch of `remote` with its commit SHA, tree SHA and fsck result."""
    with tempfile.TemporaryDirectory() as tmp:
        _git(tmp, "init", "--bare", "-q")
        listed = _git(tmp, "ls-remote", "--heads", remote)
        wanted = sorted(
            ref for line in listed.splitlines() if (ref := line.split("\t")[1]) and in_scope(ref, namespaces, history_branch)
        )
        refs: dict[str, dict] = {}
        if wanted:
            _git(tmp, "fetch", "-q", "--no-tags", remote, *[f"+{r}:{r.replace('refs/heads/', 'refs/inv/')}" for r in wanted])
            _git(tmp, "fsck", "--strict", "--no-dangling")
        for ref in wanted:
            local = ref.replace("refs/heads/", "refs/inv/")
            commit = _git(tmp, "rev-parse", local).strip()
            tree = _git(tmp, "rev-parse", f"{commit}^{{tree}}").strip()
            refs[ref] = {"commit": commit, "tree": tree}
    return {"schema": SCHEMA, "namespaces": namespaces, "history_branch": history_branch, "refs": refs}


def reconcile(source: dict, target: dict, reset_refs: frozenset[str] = frozenset(), forbid_extra: bool = False) -> dict:
    """Compare two inventories; every inventoried source ref must exist in the target unchanged.

    Maintainer-reset refs (ADR O2) are not inputs: one still in the source is flagged, one in the
    target is a forbidden restoration. `forbid_extra` makes new target refs a failure (freeze check).
    """
    src, dst = source["refs"], target["refs"]
    missing = sorted(set(src) - set(dst) - reset_refs)
    differing = sorted(r for r in set(src) & set(dst) if src[r] != dst[r])
    extra = sorted(set(dst) - set(src))
    reset_in_source = sorted(reset_refs & set(src))
    restored = sorted(reset_refs & set(dst))
    return {
        "schema": "evidence-reconciliation/v1",
        "source_count": len(src),
        "target_count": len(dst),
        "identical": sorted(r for r in set(src) & set(dst) if src[r] == dst[r]),
        "missing_in_target": missing,
        "differing": differing,
        "extra_in_target": extra,
        "reset_refs_still_in_source": reset_in_source,
        "reset_refs_restored_in_target": restored,
        "reconciled": not (missing or differing or reset_in_source or restored or (forbid_extra and extra)),
    }


def _load_reset_refs(path: str | None) -> frozenset[str]:
    if not path:
        return frozenset()
    names = (ln.strip() for ln in Path(path).read_text(encoding="utf-8").splitlines())
    return frozenset(n if n.startswith("refs/heads/") else f"refs/heads/{n}" for n in names if n and not n.startswith("#"))


def _load(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise ValueError(f"{path}: not an {SCHEMA} document")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    inv = sub.add_parser("inventory")
    inv.add_argument("--remote", required=True)
    inv.add_argument("--manifest", default="runtime_platform/benchmark/schedule/expected-run-manifest.json")
    inv.add_argument("--out", required=True)
    rec = sub.add_parser("reconcile")
    rec.add_argument("--source", required=True)
    rec.add_argument("--target", required=True)
    rec.add_argument("--out")
    rec.add_argument("--reset-refs", help="file of branch names the maintainer deleted on purpose (one per line)")
    rec.add_argument("--forbid-extra", action="store_true", help="fail when the target holds refs the source lacks")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "inventory":
            block = json.loads(Path(args.manifest).read_text(encoding="utf-8"))["evidence"]
            doc = inventory(args.remote, block["namespaces"], block["history_branch"])
            Path(args.out).write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps({"refs": len(doc["refs"])}))
            return EXIT_OK
        report = reconcile(_load(args.source), _load(args.target), _load_reset_refs(args.reset_refs), args.forbid_extra)
    except (RuntimeError, ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "detail": str(exc)}), file=sys.stderr)
        return EXIT_ERROR
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text, end="")
    return EXIT_OK if report["reconciled"] else EXIT_MISMATCH


if __name__ == "__main__":
    sys.exit(main())
