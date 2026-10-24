#!/usr/bin/env python3
"""Check the shape of one cold review against its brief.

Usage: check-review.py REVIEW BRIEF

A valid review prints PASS or FAIL, then one ITEM line per item in the
brief's "## Items" section, and exits 0. Any other shape prints
"LOST: <reason>" and exits 1. A lost review never counts as a verdict.
"""
import re
import sys

REQUIRED = ("criteria", "blocking", "coverage", "notes", "sources")
NUMBERED = re.compile(r"^\s*\d+\.\s")
# A status is its own sentence: "Met." and never "Met, see Notes."
STATUS = re.compile(r"(?:^|[.:;)]\s+|\s)(Not met|Met|Unverified)\.(?:\s|$)")
HEDGED = re.compile(r"(?:^|[.:;)]\s+|\s)(Not met|Met|Unverified)(?:[,;(]|\s\(|\s(?:on|for|with|except|but)\b)")


def lost(reason):
    print(f"LOST: {reason}")
    sys.exit(1)


def sections(lines):
    out, cur = {}, None
    for line in lines:
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            cur = m.group(1).strip().lower()
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return out


def entries(lines):
    """Numbered entries, with continuation lines joined on."""
    found, cur = [], None
    for line in lines:
        if NUMBERED.match(line):
            if cur is not None:
                found.append(cur)
            cur = line.strip()
        elif line.strip() and cur is not None:
            cur += " " + line.strip()
        elif cur is not None:
            found.append(cur)
            cur = None
    if cur is not None:
        found.append(cur)
    return found


def body(lines):
    return [l.strip() for l in lines if l.strip()]


def item_name(text):
    return text.strip().strip("`").strip()


def brief_items(path):
    with open(path) as f:
        secs = sections(f.read().splitlines())
    names = []
    for line in secs.get("items", []):
        m = re.match(r"^\s*-\s+(.+?)\s*$", line)
        if m:
            names.append(item_name(m.group(1)))
    return names


def main():
    if len(sys.argv) != 3:
        print(__doc__.strip())
        sys.exit(2)
    review, brief = sys.argv[1], sys.argv[2]
    try:
        with open(review) as f:
            lines = f.read().splitlines()
    except OSError:
        lost("no review file")
    if not lines:
        lost("empty review")
    verdict = lines[0].strip()
    if verdict not in ("VERDICT: PASS", "VERDICT: FAIL"):
        lost(f"line 1 reads {lines[0][:60]!r}")
    passed = verdict == "VERDICT: PASS"

    secs = sections(lines[1:])
    for name in REQUIRED:
        if name not in secs:
            lost(f"no '## {name.capitalize()}' section")
    if not body(secs["coverage"]):
        lost("empty Coverage section")

    crit = entries(secs["criteria"])
    if not crit:
        lost("no numbered criteria")
    # A FAIL stands on its Blocking section, so only a PASS needs every
    # criterion to carry a plain status.
    if passed:
        for c in crit:
            said = [m.group(1) for m in STATUS.finditer(c)]
            said += [m.group(1) for m in HEDGED.finditer(c)]
            if "Not met" in said:
                lost(f"PASS with a criterion at Not met: {c[:80]!r}")
            if not STATUS.search(c):
                lost(f"PASS with a hedged or missing status: {c[:80]!r}")

    blocking = body(secs["blocking"])
    if passed and blocking != ["None."]:
        lost("PASS with Blocking other than 'None.'")
    if not passed and not entries(secs["blocking"]):
        lost("FAIL with no numbered blocking finding")

    wanted = brief_items(brief)
    results = []
    if wanted:
        if "items" not in secs:
            lost("brief lists items but the review has no Items section")
        seen = {}
        for line in secs["items"]:
            m = re.match(r"^\s*-?\s*(.+?):\s*(PASS|FAIL)\b\s*(.*)$", line)
            if m:
                seen[item_name(m.group(1))] = (m.group(2), m.group(3).strip())
        for name in wanted:
            if name not in seen:
                lost(f"no Items line for {name!r}")
            state, crits = seen[name]
            if passed and state != "PASS":
                lost(f"PASS with item {name!r} at FAIL")
            results.append(f"ITEM {name} {state} {crits}".rstrip())

    print("PASS" if passed else "FAIL")
    for r in results:
        print(r)


if __name__ == "__main__":
    main()
