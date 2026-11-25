#!/usr/bin/env python3
"""attn — the list of things only Eden can do.

    attn file <key> --title T [--alive CMD] [--cwd DIR] [--body B|-]
                              [--project P] [--url U] [--source S]
    attn done  <key>              close it; the agent finished it after all
    attn list  [--json]           open items, for an agent to read
    attn purge [<key>]            close one item, or every item
    attn url                      print the page URL

Exit codes: 0 ok · 2 unknown key · 4 bad input.

This CLI never contacts the server. It writes plain files, so filing still
works when the service is down and the item appears when it comes back.

File an item only when Eden must do something himself. An item an agent could
finish is not an item.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store  # noqa: E402

EXIT_UNKNOWN_KEY = 2
EXIT_BAD_INPUT = 4


def die(code, msg):
    print(f"attn: {msg}", file=sys.stderr)
    return code


def read_body(value):
    """--body - reads stdin. Returns None when the flag is absent."""
    if value is None:
        return None
    if value == "-":
        return sys.stdin.read().strip() or None
    return value.strip() or None


def cmd_file(args):
    if not store.valid_key(args.key):
        return die(EXIT_BAD_INPUT,
                   f"bad key {args.key!r}: use [a-z0-9][a-z0-9._-]{{0,63}}")
    if not args.title or not args.title.strip():
        return die(EXIT_BAD_INPUT, "--title is required and must not be empty")
    try:
        body = read_body(args.body)
    except UnicodeDecodeError:
        return die(EXIT_BAD_INPUT, "--body must be UTF-8 text")
    with store.lock():
        until = store.suppressed_until(args.key)
        if until:
            store.append_closed({
                "key": args.key, "title": args.title,
                "closed": store.now_iso(), "reason": "suppressed",
            })
            print(f"attn: {args.key} was dismissed and is suppressed until "
                  f"{until}; not filed", file=sys.stderr)
            return 0
        store.upsert(args.key, title=args.title.strip(), body=body,
                     project=args.project, url=args.url, source=args.source,
                     alive=args.alive, cwd=args.cwd)
    return 0


def cmd_done(args):
    if not store.valid_key(args.key):
        return die(EXIT_BAD_INPUT, f"bad key {args.key!r}")
    with store.lock():
        if not store.close_item(args.key, "done"):
            return die(EXIT_UNKNOWN_KEY, f"no open item {args.key!r}")
    return 0


def cmd_list(args):
    items = store.list_open()
    if args.json:
        print(json.dumps(items, indent=2, sort_keys=True))
        return 0
    for item in items:
        print(f"{item['key']}\t{item.get('title', '')}")
    return 0


def cmd_purge(args):
    with store.lock():
        if args.key:
            if not store.valid_key(args.key):
                return die(EXIT_BAD_INPUT, f"bad key {args.key!r}")
            if not store.close_item(args.key, "purged"):
                return die(EXIT_UNKNOWN_KEY, f"no open item {args.key!r}")
            return 0
        for item in store.list_open():
            store.close_item(item["key"], "purged")
    return 0


def cmd_url(args):
    print(store.base_url())
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="attn", description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)

    p = subs.add_parser("file", help="create or update an item")
    p.add_argument("key")
    p.add_argument("--title", required=False)
    p.add_argument("--alive", help="shell command; exit 1 means resolved")
    p.add_argument("--cwd", help="directory the check runs in (default $HOME)")
    p.add_argument("--body", help="plain text detail, or - to read stdin")
    p.add_argument("--project")
    p.add_argument("--url")
    p.add_argument("--source", help="which loop filed this")
    p.set_defaults(func=cmd_file)

    p = subs.add_parser("done", help="close an item")
    p.add_argument("key")
    p.set_defaults(func=cmd_done)

    p = subs.add_parser("list", help="print open items")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)

    p = subs.add_parser("purge", help="close one item, or every item")
    p.add_argument("key", nargs="?")
    p.set_defaults(func=cmd_purge)

    p = subs.add_parser("url", help="print the page URL")
    p.set_defaults(func=cmd_url)
    return parser


def main(argv):
    args = build_parser().parse_args(argv)
    store.ensure_dirs()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
