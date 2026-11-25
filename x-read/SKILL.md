---
name: x-read
description: Use when you need to read the content of an x.com or twitter.com link - a post, a thread, or a profile. WebFetch cannot do this; x.com returns HTTP 402 to unauthenticated readers, so a link the user pastes will look broken until you run `xread`. Triggers on any x.com/ or twitter.com/ URL, a bare status id, an @handle, or a request to check what someone posted.
---

# Reading x.com links

`xread` is installed at `~/bin/xread` and is on PATH. It needs no API key, no login,
and no browser. Run it through Bash.

```bash
xread https://x.com/jack/status/20        # one post
xread <url> --thread                       # walk up to the root, print oldest first
xread <url> --media                        # include full media URLs
xread <url> --json                         # raw JSON for parsing
xread @AnthropicAI                         # profile: bio, follower count, join date
```

It accepts a full URL, a bare status id, or an `@handle`. `twitter.com`, `fxtwitter.com`
and `vxtwitter.com` URLs all parse. Tracking suffixes like `?s=20` are ignored.

## Never use WebFetch on an x.com URL

`WebFetch https://x.com/...` returns **HTTP 402 Payment Required** (measured 2026-09-01).
That is not a transient error and retrying will not fix it. Use `xread`.

## What it can and cannot do

| Task | Works |
|---|---|
| Single post text, including long posts | yes |
| Photo and video URLs | yes, with `--media` |
| Thread, walking upward from a reply to the root | yes, `--thread` |
| Profile bio and counts | yes |
| Quote-post target | yes, prints the quoted URL |
| **Replies to a post** | **no** |
| **A user's timeline** | **no** |
| **Search** | **no** |

The bottom three need a paid API. Nitter is dead: all 10 public instances tested on
2026-09-01 failed, and xcancel.com was served a cease-and-desist by X Corp on 2026-08-24.
Do not suggest a Nitter mirror. If the user genuinely needs a timeline or search, say so
and let them decide about a paid provider rather than improvising a scraper.

For a logged-in view, meaning a protected account or the user's own timeline, use the
`claude-in-chrome` skill instead. That drives Eden's real browser session.

## How it works

Two independent key-free sources, tried in order:

1. `api.fxtwitter.com/i/status/<id>` gives text, media, metrics and the parent post id.
2. `cdn.syndication.twimg.com/tweet-result` is Twitter's own embed endpoint, used when
   the first fails. Failover is tested and returns the same post from a different host.

Both are third-party or undocumented endpoints, so treat a failure as possible drift
rather than a bug in the caller. Report the failure; do not silently fall back to
scraping x.com directly.
