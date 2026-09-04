# Crucible OSS Growth & Virality Roadmap

**Status as of 2026-08-13:** Phase 0 underway — item 1 (PR regression
comment) shipped (commit `9ce1415`, pushed to `origin/main`); item 2 (badge)
shipped; item 6 (claim audit) done and it found a real bug, not a clean
pass. See §7 for the live per-item status table.
**Scope note:** this is a separate initiative from the enterprise pitch motion
(`crucible-cloud`, `CRUCIBLE_OSS_COMMERCIAL_STRATEGY.md`). That motion is
sales-led, this one is developer-acquisition-led. They reinforce each other
eventually (Cloud is the wedge this roadmap builds distribution toward) but
don't conflate the two when prioritizing work.

Kept local and untracked, same as `CRUCIBLE_OSS_COMMERCIAL_STRATEGY.md` —
internal planning, not committed until it's ready to be.

**Governing rule, unchanged through two rounds of review:** don't fabricate
the holy-shit moment. Build the capability that earns it. The real viral
product isn't a screenshot — it's a developer saying "Crucible found this,
I fixed it, Crucible proved the fix."

---

## 1. Reality check: what already exists

Before planning new work, here's what's already real and just under-promoted:

| Capability | Where | Status |
|---|---|---|
| SVG badge generation | `crucible badge`, `integrations/github/commenter.py:generate_svg_badge` | Real, works, just wasn't on the README until this session |
| GitHub Action | `action.yml` | Real, composite action, auto-uploads SARIF |
| GitHub PR commenter | `integrations/github/commenter.py` | Real, posts score to PRs today |
| Stable rule IDs | `integrations/github/sarif.py` — `CRU001`–`CRU050` | Real, but **category-level** (one ID per attack type, not 50 distinct rules), not per-technique |
| Regression detection | `crucible compare`, `crucible trend` | Real, git-based, no working-tree mutation |
| Replayable traces | `.crucible` trace files | Real |

The immediate objective is to turn these already-real capabilities into a
repeatable developer loop **before** expanding the attack engine — someone
installs Crucible and immediately sees it working inside GitHub, with zero
new engineering required to get there.

## 2. What's a fabrication risk — will not build this way

The "holy shit moment" example floated in review (a workflow command-injection
result showing `Payload reached workflow ✓ Shell command executed ✓`) does
not correspond to anything the engine does today. `SupplyChainAgent` performs
real static YAML analysis; it does not execute a live injection payload
against a target. Do not stage that output for marketing. The right fix is
building a real attack that earns that output (Phase 1), not writing the
output first — and even then, only inside an isolated fixture (see Phase 1),
never by mutating and executing content pulled from an arbitrary user repo.

## 3. Phased plan

### Phase 0 — distribution of what already exists (days, low risk)

Priority order, PR comment first — it's the strongest GitHub-native growth
mechanism and needs zero new security capability, only better framing of
data Crucible already has:

1. [x] **PR regression comment — shipped** (commit `9ce1415`, pushed).
   `GitHubCommenter.post_compare_comment()` + `_format_compare_comment()` in
   `crucible/integrations/github/commenter.py`, wired to
   `crucible compare --github-comment`. Three variants (regression /
   improvement / stable), each `CRU0XX`-tagged via `sarif._match_rule()`.
   4 new tests, 163/163 passing, verified against real git history
   (`crucible compare HEAD~3 HEAD` on this repo: `41 → 41`, no crash with
   `--github-comment` and no token configured). Found and fixed two real
   bugs along the way: both comment footers linked to the wrong repo
   (`crucible-ci/crucible` instead of `rudranpatra/crucible`), and a
   singular/plural grammar bug in the improvement-variant summary line.
   **Not yet released to PyPI** — still needs a version bump + `twine
   upload` before `pip install crucible-gym` picks it up; until then the
   demo script's caveat about checking `crucible compare --help` still applies.
2. [x] Real badge on OSS README (`badge.svg`, shipped — commit `a48d0b9`,
   39/100 F, Crucible attacking its own CI)
3. [ ] Automate badge regeneration in the `crucible-self-check` CI job so it
   doesn't go stale between manual runs — not started
4. [ ] SARIF / PR integration documentation — make the GitHub-native path the
   documented quickstart, not an appendix — not started
5. [ ] One-command quickstart UX pass — `pip install crucible-gym && crucible
   audit .` to a first meaningful result, timed (see §4, time-to-proof) — not started
6. [x] **Audit every "real" claim on public-facing copy — done, and it found
   a real bug, not a clean pass.** The pitch page's "Six agents" section
   headline read *"Every attack runs a real process against your
   pipeline"* directly above a card describing `SupplyChainAgent` as "real
   YAML analysis" — the page contradicted itself. Fixed: headline changed to
   *"Static analysis where it's reliable. Real execution where it counts,"*
   a disclaimer added under the real-output example naming which 5 of 6
   engines execute vs. which one analyzes statically, and the hero lede
   softened from "executes real adversarial conditions" (implies uniform
   execution) to "goes further where it can" (accurate: 5 real, 1 static).
   Also added: clickable hero CTAs (Install / GitHub, previously just inert
   text), a "Fix → rerun → prove" section (labeled illustrative example,
   not fabricated as live data), and reordered sections so OSS
   evidence/regression leads and the Cloud pitch follows as the natural
   next step rather than competing with it. Applied to the canonical pitch
   page and both local copies (`crucible/crucible-pitch.html`,
   `crucible-cloud/crucible-pitch-cloud.html`).

### Phase 1 — earn the "Attack it" headline (1–2 weeks, real feature work)

**Status: not started.** The pitch page now *presents* the fix → rerun →
prove concept (labeled "illustrative example," honestly not live data) —
that's copy getting ahead of engineering in a disclosed way, not a
substitute for building it. Nothing below is implemented.

Stricter design requirement than originally scoped: **the attack must
execute inside an isolated fixture, never against an arbitrary user
repository.**

```
Vulnerable fixture
       ↓
Crucible attack
       ↓
isolated execution
       ↓
observable effect
       ↓
evidence
       ↓
PASS / FAIL
```

- [ ] **A real payload-execution attack type**, built and tested against
      fixtures, not live repos:
      - vulnerable fixture → attack → **FAIL** (exploit reproduces)
      - secure fixture → attack → **PASS** (exploit blocked)
      - trace → `crucible replay` works on both
      Needs the same secure/vulnerable fixture pairing and tests as every
      other attack type in this codebase (`CONTRIBUTING.md`, strategy §19)
      — no shortcut version of this exists.
- [ ] **A canonical demo repository** (`crucible-demo`), so the website
      never needs staged terminal output again:
      ```
      01-vulnerable-workflow/
      02-secure-workflow/
      03-vulnerable-dependency/
      04-secure-dependency/
      ```
      `git clone` it, run the exact command shown on the pitch page, get the
      exact result shown. "Run the demo yourself" beats any screenshot.
- [ ] **The fix → rerun → prove loop**, designed in from the start rather
      than bolted on: the vulnerable/secure fixture pair above already gives
      this for free — run #1 against the vulnerable fixture fails, run #2
      against the fixed version passes. The PR comment format from Phase 0
      should be ready to say:
      ```
      🔥 Crucible verified the fix

      CRU-GHA-017 was previously exploitable. Now blocked.
      Security score: 87 → 96
      ```
- [ ] **Per-technique attack ID catalog.** Extend the existing `CRU001`–
      `CRU050` category IDs into per-technique IDs (e.g. `CRU-GHA-017`) with
      a docs page per attack: description, vulnerable example, reproduction,
      evidence, remediation.
- [ ] **Shareable result card — OSS-first, not hosted-first.** Local CLI
      output (`crucible attack --card` → a static PNG/SVG shared manually)
      before any hosted card-rendering service — a hosted endpoint is new
      public infrastructure and a new "what does this URL leak" question.

### Phase 2A — community (Cloud-independent, can start once Phase 1 lands)

**Status: not started** — blocked on Phase 1.

Developer-acquisition work that doesn't need enterprise pilots to justify it:

- [ ] Crucible Challenges repo — deliberately vulnerable pipelines, built to
      be solvable by the real Phase 1 attack type, not illustrative-only
- [ ] Public attack catalog + per-attack writeups (one attack = one technical
      article)
- [ ] Contribution path for community-submitted attacks
- [ ] Local shareable result card (carried over from Phase 1 if not already shipped)

### Phase 2B — scale (sequence after Crucible Cloud has real pilot orgs)

**Status: not started** — blocked on Cloud pilot traction.

Infrastructure spend that should serve an existing base, not a speculative one:

- [ ] GitHub App for one-click install (real OAuth + webhook engineering,
      no shortcut version worth half-building)
- [ ] Hosted shareable-card service, once the OSS-local version (Phase 1/2A)
      has shown people actually want to share results
- [ ] Public leaderboard — opt-in only, challenge repos or explicitly
      consenting orgs; never score arbitrary public repos without permission
- [ ] Cloud-integrated versions of the above (e.g. badge served live from
      Cloud's stored results instead of manually regenerated)

## 4. The real growth metric: time to proof

Not downloads. The question is: **how long from landing page to a developer
seeing a real security result?** Target under 5 minutes,
`pip install` to first finding.

Track the whole funnel, not just installs:

```
Landing page → install → first execution → first finding → first GitHub result
```

Instrument (as these pieces exist): PyPI installs, GitHub Action
installations, first successful run, PR comments generated, badges
installed, repeat runs, Cloud signups, Cloud-connected repositories.

## 5. Sequencing logic, spelled out

- Phase 0 ships immediately — distribution for capabilities that are
  already real, zero new credibility risk. PR regression comment leads
  because it's the strongest mechanism and needs no new security capability.
- Phase 1's real injection attack type gates any messaging that leans harder
  into "this isn't a scanner." Don't reorder this — copy ahead of capability
  is exactly the overclaim risk flagged in review. The isolated-fixture
  requirement is non-negotiable: never execute mutated content against an
  arbitrary user repo.
- Phase 2A (community) does not wait on Cloud traction — it's a separate
  acquisition channel and can run in parallel with the enterprise pitch motion.
- Phase 2B (scale infra: GitHub App, hosted cards, leaderboard) waits for an
  existing user base big enough to justify the investment.

## 6. Explicitly not doing

- Fabricated or staged attack evidence for marketing purposes
- Executing mutated/attack content against arbitrary user repositories
  outside an isolated fixture
- Scanning third-party public repositories without consent for a leaderboard
- Locking pricing to a per-repo/month number before real customer signal
  (already addressed in `crucible-cloud/docs/PRICING.md`)
- AI-generated explanations as the core value proposition — "security should
  be proven, not assumed" stays the identity

## 7. Implementation priority — live status

| # | Item | Status |
|---|---|---|
| 1 | PR regression comment | **Shipped to git** (`9ce1415`) — not yet in a PyPI release, still needs a version bump + `twine upload` |
| 2 | Automatic badge regeneration in CI | Not started |
| 3 | Quickstart / first-run UX pass | Not started |
| 4 | Canonical vulnerable demo repository | Not started |
| 5 | Design the real injection attack (fixtures, tests, isolation boundary) | Not started |
| 6 | Implement the isolated injection attack | Not started |
| 7 | Per-technique CRU IDs | Not started |
| 8 | Local shareable result card | Not started |
| 9 | Challenges repository | Not started |
| 10 | GitHub App | Not started |

Also done, outside this numbered list: real badge shipped to OSS README
(§3 Phase 0 item 2), and the public-copy claim audit (§3 Phase 0 item 6) —
both closed this session.

Item 1 is committed-and-pushable now — say the word. Item 5 is the first
genuinely new engineering commitment in this roadmap — that's the point to
write a design doc (fixtures, test plan, isolation boundary) before any
code, same as every other attack type in this codebase.
