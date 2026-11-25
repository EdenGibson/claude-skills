---
name: article
description: Add an article to Eden's phone reader. Use when Eden says "add this to my reader", "write this up as an article", "put that on my phone to read", "save this for reading later", "add an article", or asks to turn notes, a research result, a summary, or a web page into something he can read on his phone.
---

# Add an article to the reader

Eden reads on his phone at **https://devbox.tailf179c3.ts.net/read/**. The page lists every
`.html` file in `~/articles/`, newest first. A watcher (`articles.service`) rebuilds the index
within ~2 seconds. Nothing to publish, nothing to restart.

## Write it inline. Delegate the research, not the prose.

**Default: write the article yourself, in the main conversation.** Writing is cheap. A 600-word
article costs about 2k output tokens and occupies about 800 tokens of context.

Delegating the writing is usually a loss. Measured on 2026-08-16: one subagent burned **50,943
tokens** to produce 587 words, against roughly 2k inline. The subagent cannot see the
conversation, so every fact has to be restated in its prompt, then read back to check for
drift. Three passes to avoid one.

**Dispatch a subagent only when the article needs work not yet done**, a wide file sweep, a
research trawl, reading twenty files, digging through logs. Delegate *that*, and have the agent
return findings. Then write the prose yourself from what comes back. Searching is expensive
and noisy. Writing is cheap.

If the gathering is large enough that the findings themselves would flood the context, let the
research agent write the file directly. Give it the fact list, tell it to read this skill for
the voice, and check its output against the rules below before telling Eden it is ready.

## Steps

1. **Gather the source material.** Inline for a handful of files. Dispatch `Explore` or a
   `general-purpose` agent for a broad sweep.
2. **Write the file** to `~/articles/<slug>.html` using the voice and template below.
3. **Verify** it landed and renders:
   ```bash
   sleep 3 && curl -s -o /dev/null -w '%{http_code}\n' https://devbox.tailf179c3.ts.net/read/<slug>.html
   curl -s https://devbox.tailf179c3.ts.net/read/ | grep -o '<div class="t">[^<]*' | head -3
   ```
4. **Run the linter, and fix every ERROR.**
   ```bash
   article-lint ~/articles/<slug>.html
   ```
   It checks the mechanical rules: em dashes, hotlinked images, missing alt text or captions,
   bare demonstrative openers, unlabelled numbers, banned section titles, word ceiling. Exit
   code 1 means at least one ERROR. WARN is advice, so read each one and decide.
5. **Then do the re-read pass yourself.** The linter cannot judge rules 1, 8, 9 or 13. Check
   the first paragraph states the conclusion, inference is marked as inference, bad news comes
   early, and no sentence merely restates the one before it.
6. Report the title, word count, and the reader URL. Do not paste the body into chat.

## The voice

Eden's global chat rules in `~/.claude/CLAUDE.md` are tuned for a terse briefing. An article is
different: he chose to open it, and he reads it standing up on a phone. Follow the rules below,
which keep the discipline and allow prose to breathe.

Each rule below shows the failure and the fix. Match the ✅ line. When a rule and its example
disagree, the example wins.

### 1. Open with the answer, not the approach

❌ In this article I'll walk through what we found when investigating the index rebuild.
✅ The index rebuild was never the bottleneck. The 2-second poll was, and raising it to 10s cut idle CPU from 4% to 0.3% (**measured**, 1h sample).

He may read nothing after the first paragraph. Put the conclusion there. No throat-clearing,
no restating the question.

### 2. Label every number, with units and a baseline

❌ The subagent approach was much more expensive.
✅ The subagent burned 50,943 tokens against roughly 2,000 inline (**measured**, n=1), so about 25x for the same 587 words.

Every number carries **measured**, **cited**, or **estimated**. State the basis of an estimate.
Say when n=1.

### 3. Name the noun instead of opening with a bare demonstrative

❌ This is why the connection failed.
✅ The HTTPS upgrade is why the connection failed.

Applies to It, This, That, These, Those at the start of a sentence. Mid-sentence is fine.

### 4. One idea per sentence

❌ Safari upgrades http to https automatically, which means port 4340 gets a TLS handshake it cannot answer, so the page never loads.
✅ Safari upgrades http to https on its own. Port 4340 then receives a TLS handshake it cannot answer. The page never loads.

### 5. Vary sentence length on purpose

❌ The poll runs every 2 seconds. The index rebuilds. The file appears. The phone shows it.
✅ The poll runs every 2 seconds, and a rebuild follows whenever the folder signature changes. The file appears on the phone about 4 seconds after you save it.

Sentences may run to 30 words when the rhythm needs it. Four short sentences in a row read like
a telegram. Paragraphs may run to 6 sentences. Use a one-sentence paragraph for emphasis, twice
per article at most.

### 6. Say the plain word, and drop the borrowed metaphor

❌ The watcher surfaces new files and the symlink gates access to the folder.
✅ The watcher lists new files. The symlink is the only path from the web server into the folder.

Banned as verbs: surface, gate, seam, lane, drain, unlock, leverage. Write "start", not
"commence".

### 7. Put the second point in its own sentence

❌ The bind is tailnet-only, a public bind would expose the folder to the internet.
✅ The bind is tailnet-only. A public bind would expose the folder to the internet.

**No em dashes at all**, not even one carrying a single point. Eden banned the character
outright on 2026-08-16, and `article-lint` fails the file on any occurrence. Use a full stop, a
comma, or a colon. No parentheses carrying real information either. A short appositive set off
by commas is fine, as in "p95 180ms, measured".

### 8. Mark inference as inference, in the sentence

❌ Safari failed because it forced an HTTPS upgrade.
✅ Safari most likely forced an HTTPS upgrade. That explanation is inference from the symptom, not proven by a packet capture.

Write only what the source material supports. Where something is unknown, write one sentence
saying it is unknown. Never invent a number, a quote, a date, or a citation.

### 9. Lead with the bad news

❌ [three sections of detail] ... One caveat: the measurement is a single run.
✅ The 25x gap is real but rests on a single run (n=1, **measured**). The rest of this article assumes it holds.

Bad news and material caveats come early. A caveat that changes how he reads a result sits
right after it.

### 10. Title sections by what they say

❌ `<h2>Analysis</h2>`
✅ `<h2>Why the first URL failed in Safari</h2>`

### 11. Explain what he has forgotten

❌ The gate passed at 0.911 so we shipped it.
✅ The tutor accuracy gate scores recognition against 45 labelled cases. The run scored 0.911 (**measured**), above the 0.90 bar, so the change shipped.

In chat you assume full context. Here, assume he opened the article a week later.

### 12. Stop when the argument stops

❌ In summary, the reader is simple, persistent, and reachable from the phone.
✅ [the last real point, then the article ends]

No summary section, no "conclusion", no next-steps list unless Eden asked for one.

### 13. Cut the sentence that only restates the last one

❌ The rule set was not the mechanism. The second pass was.
✅ The rewrite pass produced the gain, not the rule set.

❌ Delegation earns its cost on a wide file sweep, because searching is expensive and noisy. Writing is neither.
✅ Delegation earns its cost on a wide file sweep, because searching is expensive and noisy.

The failure mode is the aphoristic closer: a short punchy sentence that restates the previous
one with more swagger. Measured on the first article written under these rules, 12 of 55
sentences carried no new information. Every one of them was a closer.

Test each sentence: **delete it and re-read the paragraph.** If nothing was lost, it stays
deleted. Apply the test hardest to any sentence under 8 words that follows a longer one.

### 14. Make the draft shorter than you want it

Write the draft, then cut it by 20% before reporting it ready. The cut is not optional and it
is not a polish pass. Delete whole sentences and whole paragraphs, never trim adjectives.

Target the shortest length the argument survives at. Treat 900 words as a ceiling, not a goal.
An article that says one thing in 350 words beats the same thing in 800.

Delete on sight:
- Any sentence that begins "The corollary is", "The cause is structural", "Two habits are worth copying".
- Any paragraph whose first sentence promises what the paragraph will do.
- Any closing flourish. The last sentence of a section should carry the section's newest fact.

### 15. Strip the AI tells

❌ It is important to note that this pivotal change unlocks a seamless, multifaceted improvement.
✅ The change cut p95 from 420ms to 180ms (**measured**, n=200).

❌ The fix was not just faster, but fundamentally more correct.
✅ The fix was faster. The fix was also correct, which the old path was not.

Eden reads these knowing a model wrote them. Prose that also *sounds* like a model wastes his
attention on the style instead of the argument.

**Excess vocabulary.** Kobak et al. tracked word frequency across 15 million PubMed abstracts
from 2010 to 2024 and found 774 words whose use jumped after LLMs arrived, estimating at least
13.5% of 2024 abstracts were LLM-processed (**cited**,
[Science Advances](https://www.science.org/doi/10.1126/sciadv.adt3813)). Avoid the worst of
them: delve, intricate, notably, showcase, underscore, pivotal, realm, tapestry, beacon,
multifaceted, meticulous, commendable, paramount, myriad, testament, garner, foster, harness,
unveil, elevate, seamless, vibrant, robust, crucial, comprehensive, nuanced, transformative,
leverage, landscape, navigate, embark, unlock, holistic.

None of those words is wrong. Each is a word a model reaches for and a person usually does not.
A technical name is exempt, so a "test harness" stays a test harness.

**Filler openers.** Delete on sight: "it is important to note", "it is worth noting", "when it
comes to", "plays a crucial role", "a testament to", "in the realm of", "one of the most".
Every one of them can be cut with no loss.

**The negation-contrast template.** "Not just X, but Y." "It's not X, it's Y." "Not only X but
also Y." The construction promises a reversal and usually delivers a synonym. State the thing
directly instead. No corpus study measures this pattern, so it is inference from style, not a
cited finding.

**Em dash rate.** Human writers use roughly one per 500 words, against one per 50 to 80 words
for 2023-2024 models, so about 3x to 5x (**cited**,
[Memeburn](https://memeburn.com/how-to-detect-ai-content/), popular-press aggregation rather
than a peer-reviewed count). Eden has banned the character outright, so the rate is zero here.

**Uniform rhythm is the strongest tell.** Machine prose organises too evenly: every paragraph
the same length, every section the same shape, three bullets under every heading. Reporting
found structure to be a better signal than vocabulary (**cited**,
[Hunting the Muse](https://huntingthemuse.net/library/how-to-tell-if-writing-is-ai)). Vary
paragraph length deliberately. Break the pattern where the argument breaks.

`article-lint` checks all of this, and errors when four or more excess words appear in one
article, or on any filler phrase.

### 16. Make it understandable before you make it short

❌ The rebuild is driven by a 2-second poll of the folder, which, because the watcher compares a signature rather than mtimes alone, catches deletes too.
✅ The watcher polls the folder every 2 seconds. It compares a signature of the whole folder, not just modification times, so a deleted file is caught as well.

Brevity and understanding are different goals. Where they fight, understanding wins. Cut a
whole point rather than the sentence that makes a point land.

**Same thing, same word, every time.** Call the linter the linter in every sentence. Never
reach for "the tool" or "the checker" to avoid repeating yourself. A changed word makes Eden
stop and ask whether you mean something new.

**Known first, new second.** Open a sentence with what he already knows, then attach the new
fact. Meyer found readers go faster and retain more when new material anchors to existing
knowledge (**cited**).

**Keep the subject next to its verb.** Long qualifying phrases go after the main clause. A long
opening clause makes him hold it in memory before learning what the sentence is about.

**One worked example beats a paragraph of explanation.** Give the real values.

**Define a term the first time it appears**, in four words or fewer, in the same sentence.
Standard vocabulary he uses daily needs no definition.

**Name the paragraph's idea in its first sentence.** The rest supports that sentence.

**Link the sentences.** Coherence predicts comprehension better than any other single feature
(**cited**, Armbruster; Kintsch). Repeat the linking noun instead of trusting inference.

Word choice is the small lever. The ISO plain language standard runs to roughly 485 provisions,
and only about 7% concern word choice (**cited**). Structure and order decide understanding, so
rules 1, 10, 12 and this one matter more than rules 6 and 15.

### Also true, no example needed

- Active voice. Simple tenses. Never a compound tense like "has been failing".
- Transitions between sections are wanted. An article needs a thread to follow.
- Shortest length the argument survives at. 900 words is a ceiling, not a goal.
- Link every source inline with a real `<a href>`. He is on a phone and cannot grep.

### Check before you report it ready

Re-read the draft against rules 1, 2, 3, 8, 13, 15 and 16. Those five fail most often. Then run the 20% cut in rule 14. Guidelines alone do
not produce the result, writing under an explicit readability standard still missed the target
in the Cochrane plain-language studies, and only a rewrite pass fixed it. Do the pass.

## Images

An article earns an image when the image carries information the prose cannot. A chart of the
numbers, a screenshot of the actual UI, a diagram of the flow, the photograph the article is
about. Decorative stock photography is worse than nothing on a phone, because it costs a scroll
and says nothing.

**Never hotlink.** A remote `<img src="https://...">` breaks when the far end moves the file,
and a plain-http source is blocked as mixed content on the HTTPS reader page. Always pull the
image local first:

```bash
article-image <slug> <url-or-local-path> [name]
# prints: src="img/<slug>/<name>.jpg"   213KB 1280x1278
```

The helper downloads or copies the file, strips metadata, caps it at 1400px wide, re-encodes at
quality 82, and warns above 900KB. Files land in `~/articles/img/<slug>/`, which the reader
serves and the article list ignores. `icon-32.png` and `icon-180.png` sit beside `reader.css`
and are ignored the same way; they are the reader's favicon and its home-screen icon, copied
from `~/.local/share/server-icons/` by `make-server-icons.py`.

### Finding one

**Licences do not apply here.** The reader is a private page on Eden's tailnet with exactly one
reader. Take the best image for the point, from wherever it lives. Never spend a search, a
sentence, or a caption on licence terms.

Dispatch an agent to search when the article needs a picture you do not already have. Tell it to
return **direct image file URLs** ending in `.jpg`, `.png`, `.svg` or `.webp`, each with the page
it came from. A search results page is not an image URL, and an agent that returns one has not
finished the job.

Pick on relevance alone, in this order:

1. **Something you can generate.** A chart from the real numbers, a screenshot of the running
   app, a diagram. Truthful and exactly on topic, so it always wins.
2. **The primary source itself.** The figure from the paper, the vendor's own architecture
   diagram, the actual repo screenshot, the real dashboard.
3. **Wikimedia Commons.** Stable URLs and rarely hotlink-blocked, so fetches tend to work.
4. **Anywhere else.** A blog, a news site, a docs page. Fine.

Two practical failures, neither about copyright. Some hosts block a non-browser fetch and return
403 or an HTML error page, so check what `article-image` actually saved. And a thumbnail from a
search page is usually 150px wide, which looks broken on a phone. Get the full-size file.

### Markup

Every image is a `<figure>` with a caption. The caption says what the image shows, and links the
page it came from so Eden can click through to the original.

```html
<figure>
  <img src="img/my-slug/latency.png" alt="Line chart, p95 latency falling from 420ms to 180ms after the index change">
  <figcaption>p95 latency across the deploy, n=200 (<strong>measured</strong>). Source: <a href="https://example.com/dashboard">Grafana</a>.</figcaption>
</figure>
```

- **`alt` is required and describes the content**, not the file. "Line chart, p95 falling from
  420ms to 180ms" beats "chart".
- Add `class="shot"` to a UI screenshot: `<figure class="shot">`. A hairline border keeps a
  white screenshot from bleeding into the page.
- Two images side by side: wrap them in `<div class="pair">`. The pair stacks below 30rem, so
  it still works on a phone.
- Caption every image. An uncaptioned image on a phone is a puzzle.

### Budget

Two or three images in a 700-word article. One is usually right. Keep the whole article under
about 1MB, because he opens these on cellular. Check with:

```bash
du -sh ~/articles/img/<slug>/
```

## Template

Always link `reader.css`. Never write a `<style>` block, the stylesheet handles phone
typography, dark mode, and iPhone safe-area insets.

```html
<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<title>Short specific title</title>
<link rel="stylesheet" href="reader.css">
<link rel="icon" type="image/png" href="icon-32.png">
<link rel="apple-touch-icon" href="icon-180.png">
<article>
<h1>Short specific title</h1>
<p class="meta">16 Aug · source: <a href="https://example.com">example.com</a></p>

<p>First paragraph states the conclusion.</p>

<h2>Why the index was wrong</h2>
<p>Body.</p>

<p><a href="./">Back to the list</a></p>
</article>
```

The list title comes from `<title>`, falling back to the first `<h1>`. Keep them identical.
Slugs are lowercase and hyphenated, with no date prefix, the list already sorts by mtime.
Read time assumes 220 words per minute.

`reader.css` styles plain tags. The only extra class is `.meta`, for a small grey byline or
caption. Do not invent classes; they render unstyled. Use `<blockquote>` for quoted source
text and `<pre><code>` for code.

## Removing or updating

Overwrite the file to update it. Delete it to remove it from the list.

```bash
rm ~/articles/<slug>.html    # gone from the phone within ~2s
```

## If something looks broken

- Nothing appears in the list: `systemctl --user status articles.service`
- Page will not load on the phone: he must use the **https://** tailnet URL. Safari refuses
  the plain `http://devbox:4340/read/` address.
- Rebuild the index by hand: `~/.local/bin/article-index.py`

## Change history

- **2026-08-16**, Voice section rewritten from 25 abstract rules into 12 paired ❌/✅ examples.
  Paired do/don't examples are the most consistently recommended format across
  [Write the Docs](https://www.writethedocs.org/guide/writing/style-guides/),
  [HubSpot's style-guide guidance](https://blog.hubspot.com/blog/tabid/6307/bid/31247/the-simple-template-for-a-thorough-content-style-guide.aspx),
  and [Anthropic's prompting docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/be-clear-and-direct),
  which all hold that examples convey style better than descriptions. The
  [Cochrane plain-language studies](https://abstracts.cochrane.org/2013-quebec-city/readability-cochrane-breast-cancer-group-plain-language-summaries)
  are why a re-read pass is now mandatory: writing under explicit guidance still missed the
  target, and only a rewrite fixed it.
- **2026-08-16**, Switched from always-delegate to write-inline. One subagent cost 50,943
  tokens for 587 words against roughly 2,000 inline (**measured**, n=1).
- **2026-08-16**, Added rules 13 and 14 after the first article read padded. Measured: 12 of
  55 sentences carried no new information, all of them short closers restating the prior
  sentence. Word target changed from 400-1200 to a 900 ceiling, and a mandatory 20% cut added.
- **2026-08-16**, Added image support. `article-image` pulls any image local before use,
  because a hotlink rots and a plain-http source is blocked as mixed content on the HTTPS
  reader page. Figure/caption/pair styles added to `reader.css`.
- **2026-08-16**, Dropped all licence rules. The reader is private with one reader, so licence
  terms cost search effort and constrain image choice for no benefit. Sourcing is now ranked on
  relevance alone. Source links stay in captions, so Eden can click through to the original.
- **2026-08-16**: Added rule 16, understandability. Consistent terminology, known-before-new
  order, subject next to verb, worked examples, defined terms, linked sentences. Prompted by the
  ISO plain language finding that only ~7% of its 485 provisions concern word choice, so the
  earlier rules were tuned on the small lever.
- **2026-08-16**: Added rule 15, the AI tells. Excess-vocabulary list from Kobak et al.
  (Science Advances, 15M PubMed abstracts), plus filler phrases, the negation-contrast template,
  and a uniform-paragraph-length check. All enforced by `article-lint`.
- **2026-08-16**: `article-lint` added and wired in as a required step, so the greppable rules
  stop eating the re-read pass. Em dashes banned outright at Eden's request, and swept from
  every article, script and this file.
- **2026-08-16**, Skill created.
