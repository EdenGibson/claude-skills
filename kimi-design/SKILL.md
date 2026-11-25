---
name: kimi-design
description: Route visual/HTML design generation to Kimi K3 via the locally-installed Kimi Code CLI, instead of generating it yourself. Use when Eden asks to design something "with Kimi", "on Kimi Code", "using K3", wants a second opinion or alternative variant from a different model, or when a from-scratch visual mockup would benefit from K3's frontend strength. Output lands in ~/design-lab/ and auto-appears on his laptop via the html-design live server. Two modes - delegate (you prompt Kimi headlessly, then review) and handoff (you prep the workspace, Eden drives Kimi interactively). Not for editing real Derive components; that stays with hifi-design.
user_invocable: true
---

# kimi-design — delegate visual design to Kimi K3

Kimi Code CLI is installed at `~/.kimi-code/bin/kimi` (on PATH via `.bashrc`). It has a
real headless mode, so K3 can be driven as a subprocess and treated as a design
generator you orchestrate — or handed to Eden to drive himself.

**Why bother:** K3 is #1 on LMArena's Frontend Code Arena (1,679 Elo, beat Fable 5
in 76% of blind matchups, first in 6 of 7 frontend domains). That benchmark scores
*human preference on generated pages* — visual hierarchy, spacing, composition —
which is exactly the axis where a second model is worth the round trip.

**Why not always:** on independent aggregate benchmarks it trails (Intelligence
Index 57 vs Fable's 60), it's slow (~35 tok/s, long-horizon tasks run ~2x Fable),
and it measures **worse on accessibility and semantic HTML**. So: K3 generates,
you review. Never ship its output unreviewed.

## Preflight (do this first, every time)

```bash
kimi doctor                       # binary healthy? config present?
```

If `~/.kimi-code/config.toml` and `~/.kimi-code/auth.json` are both missing, Kimi is
**not authenticated** and nothing below will work. Tell Eden:

> Run `kimi login` (device-code flow — needs a browser). One time.

You cannot do this for him. Stop and ask; don't fake it or fall back silently.

**Model tiers:** `k3` (1M ctx) and `k3-256k` require a Moderato+ plan.
`kimi-for-coding` (K2.7 Code) is available on all plans. If `-m k3` errors on
entitlement, retry once with `-m kimi-for-coding` and **say in your report that you
downgraded** — K2.7 does not carry K3's arena result.

## IMPORTANT — network needs an unsandboxed shell

Default Bash tool calls are sandboxed and **have no outbound network**, so `kimi`
will fail with a connection error inside one. Every `kimi` invocation here must run
with `dangerouslyDisableSandbox: true`. (Verified 2026-08-04: `api.moonshot.ai`
returns 200 in 0.28s unsandboxed, and is unreachable sandboxed.)

## Mode A — delegate (default)

You stay the orchestrator. Kimi generates, you critique and iterate.

### 1. Start the live server
Reuse the `html-design` skill's server — do not build another one:
```bash
python3 ~/.claude/skills/html-design/server.py ~/design-lab 4321
```
Run in background; it no-ops if already up. URL is `http://devbox:4321`.

### 2. Write a brief file
Put the design brief in `/tmp/kimi-brief.md`. Write it as a **spec, not a chat
message** — Kimi gets it cold with no conversation history. Always include:

- What the page is and who it's for.
- Concrete visual direction (mood, density, palette intent) — not "make it nice".
- **The constraints K3 is measurably weak on**, spelled out explicitly:
  - semantic HTML5 landmarks, real heading order, `alt` on every image
  - visible focus states, keyboard-operable interactive elements
  - WCAG AA contrast (4.5:1 body, 3:1 large text)
  - `@media (prefers-reduced-motion: reduce)` honoured
- Self-contained single file, inline CSS/JS, no build step.
- **If it's Derive-flavoured:** paste the actual token values you want used. Kimi
  cannot see `derive-web/app/globals.css` and will invent hex codes otherwise.

### 3. Run it
```bash
bash ~/.claude/skills/kimi-design/run-kimi.sh pricing-dark.html /tmp/kimi-brief.md k3
```
Name the target after the design and never `current.html` — the design folder is
shared by every parallel session, so a shared filename is overwritten by whoever
writes last. `html-design`'s SKILL.md has the `set -C` snippet that claims a free
name.
`run_in_background: true` + `dangerouslyDisableSandbox: true`. K3 is slow — expect
minutes, not seconds. The helper refuses to run if the target dir is a git repo,
and fails loudly if the file never appeared.

Use a variant filename (`kimi-v2.html`) when Eden wants alternatives side by side —
`html-design`'s gallery at `/` picks them up automatically, newest first.

### 4. Review before you report — this is the point of the mode
Read the generated file and check, at minimum:
- Contrast of every text-on-colour pair, computed not eyeballed.
- Heading order, landmarks, focus states, `alt` text.
- Reduced-motion block present if anything animates.
- No invented brand hexes if tokens were specified.

Fix what's broken yourself with Edit — that's cheaper than another K3 round trip,
and a11y is where you're stronger. Then tell Eden what Kimi produced, what you
changed, and what it got wrong. **Report the a11y defects you found even after
fixing them** — that's the running evidence on whether K3 is worth using here.

### 5. Iterate
Small changes: edit the file directly, server live-reloads.
Re-generate through Kimi only for a genuinely different direction.

## Mode B — handoff (Eden drives)

When Eden wants to work *in* Kimi rather than have you relay. You prep, he drives.

1. Start the live server (step 1 above) so whatever he does shows on his laptop.
2. Write any context he'll want into `~/design-lab/BRIEF.md`.
3. Print the command for him to paste into a terminal:

```bash
cd ~/design-lab && kimi -m k3 --add-dir ~/design-lab
```

Add `--plan` to start in plan mode, `-c` to continue the previous session in that
directory, `-y` to auto-approve tool calls without full autonomy.

Then get out of the way. Don't run Kimi yourself in this mode.

## Scope limits

- **`~/design-lab/` only.** Never run `--auto` Kimi inside `~/code/Derive` or any
  other repo — an autonomous non-Anthropic agent with write access to a real
  codebase is not something to do casually. Promoting a mockup into a real
  component is `hifi-design`'s job, done by you, reviewed normally.
- **Never `preview` design-lab** (4340 is for finished artifacts; 4321 owns this).
- Don't put secrets in mockups — the server is open to the whole tailnet.

## Useful kimi flags (v0.32.0)

| Flag | Use |
|---|---|
| `-p, --prompt` | one-shot non-interactive, prints response |
| `--auto` | fully autonomous, never asks questions (required headless) |
| `-y, --yolo` | auto-approve tool calls, may still ask questions |
| `--output-format stream-json` | machine-readable transcript |
| `--add-dir <dir>` | add a workspace directory (repeatable) |
| `--skills-dir <dir>` | load skills from a directory — Kimi reads Claude-style Markdown skills |
| `--agent-file <path>` | load an agent definition from a Markdown file |
| `-m <alias>` | `k3`, `k3-256k`, `kimi-for-coding`, `kimi-for-coding-highspeed` |
| `-S`, `-c` | resume / continue a session |

`--skills-dir` is the interesting one: Derive's design-system rules can be handed
to Kimi as a skill directory rather than pasted into every brief. Untested as of
2026-08-04 — try it once auth works, and if it takes, point it at a trimmed
design-system skill instead of inlining tokens in the brief.

## Status (2026-08-04)

Built but **never executed end-to-end** — Kimi Code is installed (v0.32.0) and the
network path is verified, but the account has never been logged in, so no run has
happened. First real use is also the first test: expect to fix things.
