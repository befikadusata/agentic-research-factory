# Factotum — Visual Identity & Design Language

> **Factotum** — an AI-powered market research automation platform. A LangGraph
> supervisor orchestrates specialized agents (Strategist, Researcher, Analyst,
> Writer, Editor…) through research pipelines in real time.
>
> This document defines the **visual language**: the why behind the palette,
> typography, motion, and the signature components. For token values, code, and
> the Tailwind wiring, see [`factotum-implementation.md`](./factotum-implementation.md).

---

## 1. Brand essence

Factotum sits **between a Bloomberg terminal and a modern dev tool**. It is a
serious instrument for professionals who watch machines think. The interface has
two moods and must switch between them cleanly:

| Mode | Feeling | Trigger |
| --- | --- | --- |
| **Alive** | Agents are working. Subtle motion, node pulses, streaming text, traveling data. | A run is executing. |
| **Still** | The human is in control. Motion drains away, contrast rises, one clear action. | A HITL checkpoint pauses the run. |

Everything below serves that contrast. Motion is **diagnostic, never
decorative** — a pulse means "this agent is active right now," not "look how
polished we are."

### Design principles

1. **Dense but breathable.** Terminal-grade information density, but every panel
   has air. Whitespace is structural, not generous.
2. **Cool, never warm.** Obsidian base, cool off-whites, cold cyan. No cream, no
   warm gray, no warm white — ever. Warmth is reserved *exclusively* for the
   amber HITL moment, which is why it reads as an interruption.
3. **Colour carries meaning.** Cyan = system/primary. Violet = agent thinking.
   Amber = human turn. Green = done. Red = failed. A user should be able to read
   run state from colour alone.
4. **Motion is state.** If something moves, it is because something is happening.
   When the human takes over, the UI goes quiet.
5. **Monospace for truth.** Anything the machine emits — logs, timestamps,
   token counts, IDs, costs — is monospace. Prose the human reads is sans.

---

## 2. Colour

### 2.1 The base — obsidian / navy

A single cool blue-black spine runs the whole product. It is nearly black at the
canvas and lifts, step by step, toward the user. Surfaces are distinguished by
**value + a hairline border**, not by drop shadows (shadows read warm and soft;
Factotum reads cold and precise).

```
surface-0  canvas        ▓ #04060A   deepest, behind everything
surface-1  panel         ▓ #0A0F17   app chrome, sidebars
surface-2  card          ▓ #0E141E   the default "thing" surface
surface-3  raised/input  ▓ #131B27   inputs, hover, nested cards
surface-4  overlay       ▓ #19222F   popovers, menus, active rows
```

### 2.2 The primary — electric cyan

Cold, high-energy cyan is the system's voice: the supervisor, primary actions,
active states, focus rings, links, the pulse of a working node.

```
cyan-300  #7FF3FB   glow highlight
cyan-400  #3DE3F0   ← PRIMARY. actions, active agent, focus
cyan-500  #14C6D9   pressed / hover-down
cyan-700  #0A7C8C   muted cyan, borders
```

Cyan is **loud** — use it sparingly so it stays loud. A screen with cyan
everywhere has no active state.

### 2.3 The two secondaries

| Colour | Role | Why |
| --- | --- | --- |
| **Muted amber** `#E9B25C` | **Human-in-the-loop.** The interrupt colour. HITL cards, "awaiting you" badges, paused nodes. | Warmth = a human is needed. It is the *only* warm thing on screen, so it can't be missed. |
| **Soft violet** `#A38BF5` | **Agent activity / thinking.** Reasoning states, agent-identity accents, "the model is generating." | Violet reads as cognition — distinct from system-cyan and from done-green. |

### 2.4 Neutrals — cool grays & cool off-white

Text and quiet UI live on a blue-tinted gray ramp. The lightest is a **cool
off-white**, never a true or warm white.

```
gray-050  #E9EEF4   primary text (cool off-white)
gray-300  #93A2B4   secondary text
gray-500  #556575   muted text, idle outlines, disabled
gray-600  #3E4C5C   dividers
```

### 2.5 Feedback palette

```
success  mint    #3FD69A   complete, healthy
error    rose    #F26478   failed, destructive
warning  amber   #E9B25C   caution (shares HITL hue by design)
info     cyan    #3DE3F0   neutral system notice
```

### 2.6 Agent identity hues

Each agent owns **one fixed, muted hue** used for its log prefix, its avatar dot,
and its node accent. These are deliberately desaturated so seven of them can
coexist in a log stream without vibrating. They are *identity*, not *status* —
an agent keeps its hue whether idle, active, or done.

```
Supervisor   #5FC7D4   cool cyan-gray
Strategist   #A38BF5   violet
Researcher   #6BA8E0   muted blue
Analyst      #58C6A6   muted teal
Reviewer     #C9A96A   muted gold
Writer       #B58BD0   muted mauve
Editor       #7E93C4   indigo-gray
```

> **Rule:** status colours (cyan/amber/green/red) always override identity hues.
> A Researcher node that errored is **red**, not muted-blue. Identity only shows
> in neutral contexts (log prefix, roster).

### 2.7 Contrast & accessibility

- Primary text (`gray-050`) on any surface ≥ **7:1** (AAA).
- Secondary text (`gray-300`) on surfaces ≥ **4.5:1** (AA).
- **Never encode state in colour alone.** Every status colour is paired with an
  icon or glyph: active = pulse ring, complete = ✓, error = ✕, paused = ▮▮
  (pause bars), idle = hollow outline. Colour-blind users read the glyph.
- Focus rings are a 2px `cyan-400` ring + 2px offset, on every interactive
  element, always visible on keyboard focus.

---

## 3. Typography

A **mono + sans pairing** carries the "data instrument" identity.

| Role | Family | Notes |
| --- | --- | --- |
| **Sans (UI/prose)** | `Inter` → fallback `Plus Jakarta Sans` | Neutral, precise, terminal-adjacent. Recommend migrating from Plus Jakarta (geometric/friendly) to Inter/Geist for a colder, more instrumental read. |
| **Mono (data/logs)** | `JetBrains Mono` → `IBM Plex Mono` | Timestamps, token counts, costs, IDs, log bodies, code, citation locators. |

### Type scale (1.20 minor-third, 4px rhythm)

```
display   32 / 40   -0.02em   sans 600   dashboards, hero counts
h1        24 / 32   -0.01em   sans 600
h2        20 / 28   -0.01em   sans 600
h3        16 / 24    0        sans 600
body      14 / 22    0        sans 400   ← default UI text
body-sm   13 / 20    0        sans 400
label     11 / 16    0.06em   sans 600 UPPERCASE   section eyebrows
mono-sm   13 / 20    0        mono 400   log lines, values
mono-xs   11 / 16    0        mono 400   timestamps, locators
```

Prefer **13–14px** as the working size. Density comes from tight line-height and
spacing, not tiny type.

---

## 4. Space, shape, elevation

- **Grid:** 4px base. Spacing steps 4 / 8 / 12 / 16 / 24 / 32 / 48.
- **Radii:** `sm 4px` (inputs, pills-internal), `md 8px` (cards, buttons),
  `lg 12px` (panels, HITL card), `pill 999px` (badges, citation pills).
- **Elevation is borders + glow, not shadows.** Depth is read from surface value
  and a `1px` hairline (`gray-600` at low opacity). The only "shadow" that
  matters is the **cyan glow** on an active node and the **amber glow** on a HITL
  card — light as signal, not as drop-shadow decoration.

```
glow-active   0 0 0 1px cyan-400, 0 0 16px -2px cyan-400/45   (working)
glow-hitl     0 0 0 1px amber-400, 0 0 24px -4px amber-400/35 (paused, human)
hairline      inset 0 0 0 1px gray-600/40
```

---

## 5. Signature components

Wireframes are indicative; exact tokens and code live in the implementation doc.

### 5.1 Agent Pipeline Visualizer

A horizontal node-graph of the active agent chain. The **spine of the product** —
it must communicate run state at a glance from across a room.

```
  ┌─────────┐        ┌─────────┐        ┌─────────┐        ┌─────────┐
  │   ✓     │──●────▶│  ((●))  │───────▶│    ·    │───────▶│    ·    │
  │Superv…  │        │Research…│        │Analyst  │        │Writer   │
  └─────────┘        └─────────┘        └─────────┘        └─────────┘
   complete            ACTIVE             idle               idle
   solid + ✓         cyan pulse ring    dim outline        dim outline
                     edge: traveling
                     dot animates →
```

**Node states**

| State | Fill | Border | Glyph | Motion |
| --- | --- | --- | --- | --- |
| idle | none | `gray-500` dim | — | none |
| active | `cyan-400/10` | `cyan-400` | agent icon | **pulsing glow ring** (~1.6s) |
| complete | `success/12` | `success` | ✓ | none (settled) |
| error | `error/12` | `error` | ✕ | one-shot shake on entry |
| paused-hitl | `amber-400/12` | `amber-400` | ▮▮ | slow **amber breathing** |

**Edges** are `1px` hairlines. When data flows between two agents, a **cyan
traveling dot** runs source → target along the edge (~900ms, loops while
transferring). Idle edges are static `gray-600`. Completed edges are a solid
`cyan-700` fill (the path already taken).

**Progress bar variant** (compact / mobile / header): the same state model
collapsed into a segmented bar — one segment per agent, filling cyan as the run
advances, the active segment carrying the pulse, an amber segment when paused.

### 5.2 HITL Checkpoint Card — *the most human component*

When the pipeline hits a checkpoint, the run **stops** and this card takes over.
This is the emotional center of the product: the machine pauses and hands you the
controls. Everything about it should feel like a held breath.

```
  ┌──────────────────────────────────────────────────────────────┐
  │ ▮▮  CHECKPOINT · your review needed          amber eyebrow    │  ← amber
  │──────────────────────────────────────────────────────────────│    top rule
  │                                                                │
  │  Draft summary — Competitor Brief                              │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │ Acme Corp leads on pricing transparency but trails on   │  │  surface-3
  │  │ enterprise SSO. Three gaps identified in onboarding…    │  │  read-only
  │  └────────────────────────────────────────────────────────┘  │
  │                                                                │
  │  Corrections (optional)                                        │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │ Tighten the pricing section and add a SOC2 note…    ▋   │  │  textarea
  │  └────────────────────────────────────────────────────────┘  │  focus=amber
  │                                                                │
  │              [ Discard ]        [  Continue run  → ]           │  ← primary
  └──────────────────────────────────────────────────────────────┘
      amber hairline border + soft amber glow · pipeline dims behind
```

Behaviors that make it feel human:
- **The pipeline stills.** All node pulses and traveling dots freeze; the
  background dims ~40%. The card is the only lit thing.
- **Warm interrupt.** Amber border + faint amber glow — the sole warm element in
  the whole UI, so it registers as *a person is needed here*.
- **Entry is a settle, not a slam.** Card eases in over ~400ms with a gentle
  scale-from-0.98, like the system exhaling and waiting.
- **Primary action is unmistakable:** `Continue run →` in cyan (system resumes),
  with the arrow signaling forward motion. Secondary `Discard` is quiet/ghost.
- The textarea focus ring is **amber**, not cyan — while the human holds the pen,
  even the accent is on their side.

### 5.3 Real-time Agent Log Stream

Terminal-style scrolling feed. This is where "alive" lives most literally.

```
 ┌──────────────────────────────────────────────────────────────┐ ░ scanline
 │ 14:02:11.204  supervisor  routing → Researcher                │ ░ texture
 │ 14:02:11.881  researcher  fetching 6 sources (tavily)         │ ░ over
 │ 14:02:13.02   researcher  ▸ scored 41 chunks, reranking       │ ░ surface
 │ 14:02:14.55   analyst     synthesizing competitive matrix …   │ ░
 │ 14:02:16.10   analyst     ▮▮ checkpoint raised                │ ░
 │ ▋                                                              │ ░ live caret
 └──────────────────────────────────────────────────────────────┘
   ↑ monospace   ↑ agent hue prefix (fixed)   ↑ new lines fade+slide in
```

- **Timestamps** in `mono-xs`, muted. **Agent prefix** in that agent's fixed
  identity hue (§2.6), fixed-width column so the eye can scan one agent.
- **New lines stream in** with a 140ms fade + 4px slide-up. A blinking cyan
  **caret** sits at the tail while the stream is live; it disappears when the run
  settles or pauses.
- A **subtle scanline texture** (2px repeating, ~3% opacity) overlays the panel
  background — enough to say "CRT/terminal," not enough to hurt. Disabled under
  `prefers-reduced-motion` and never animated.
- Auto-scroll pins to bottom; scrolling up detaches and shows a "jump to live ↓"
  affordance.

### 5.4 Research Playbook Selector

Three cards, chosen at run start. Equal weight, cool by default, cyan on select.

```
 ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
 │ ◇             │   │ ◈             │   │ ✦             │
 │ B2B Intel     │   │ Competitor    │   │ Founder       │
 │               │   │ Brief         │   │ Strategy      │
 │ Target accts, │   │ Feature audit,│   │ Market segs,  │
 │ buyer criteria│   │ pricing, gaps │   │ ARR, rivals   │
 │               │   │               │   │               │
 │ ~6 agents     │   │ ~5 agents     │   │ ~7 agents     │  ← mono meta
 └───────────────┘   └───────────────┘   └───────────────┘
   surface-2, hairline · hover lifts to surface-3 · selected = cyan border+glow
```

Selected card gets a `cyan-400` border, faint cyan glow, and a small ✓. Each has
a distinct monochrome glyph so they're recognizable pre-read.

### 5.5 Citation pill

Inline, monospace, evidence you can trust and click.

```
 ⟦ 3 ⟧ acme-pricing.pdf · p.12      ← pill: surface-3, cyan-700 border
```

- Compact `pill` radius, `mono-xs`. A cyan index chip, then a muted source +
  locator. Hover reveals the snippet in a `surface-4` popover. Broken/unverified
  citations flip the index chip to `error` — trust is visible.

### 5.6 Cost audit micro-widget

A quiet, always-available readout of spend — dev-tool honesty about the meter
running.

```
 ⌁ 24.1k tok · $0.083          ← mono, gray-300, ⌁ glyph cyan
```

Sits in the run header or footer. Monospace, understated. Expands to a per-agent
breakdown popover (bar per agent, tokens + cost) on click. Turns `warning` amber
if a run crosses a configured budget threshold.

### 5.7 Tenant workspace switcher

```
 ┌────────────────────────┐
 │ [NW]  Northwind Co     ▾│   ← surface-2 trigger, 2-letter mono monogram
 └────────────────────────┘
      opens surface-4 menu: workspaces + role badge (viewer/operator/admin)
```

A compact monogram + name trigger. Menu lists workspaces with a role badge
(`viewer` gray / `operator` cyan / `admin` violet). Deliberately understated — it
orients, it doesn't compete with the pipeline.

---

## 6. Motion & interaction

### The core rule: *alive when agents run, still when humans decide.*

| Situation | Motion budget |
| --- | --- |
| Run executing | Node pulse, traveling edge dots, streaming log lines, live caret. All low-amplitude, looping, purposeful. |
| HITL checkpoint | **Everything freezes.** Background dims. Only the card's soft amber breath remains. Stillness = your turn. |
| Run complete | Motion resolves: pulses stop, final node settles to ✓, caret vanishes. Calm. |
| Error | One decisive one-shot (node shake / red flash), then still. No looping alarm. |

### Timing & easing (see implementation for exact tokens)

- Durations: `instant 80ms · fast 140ms · base 220ms · slow 400ms · deliberate 700ms`.
- Standard ease `cubic-bezier(0.2, 0, 0, 1)`; entrances decelerate, exits accelerate.
- **Loops** (pulse, breath, caret) are slow and shallow (1.6–2.4s) so a room full
  of them never feels frantic.

### `prefers-reduced-motion`

A first-class path, not an afterthought:
- Node pulse → a static cyan ring (state still legible).
- Traveling edge dots → a solid cyan edge fill.
- Streaming lines → appear instantly, no slide/fade.
- Scanline, breathing, caret blink → **off**.
- HITL entry → instant swap, no scale.

State is **never** conveyed by motion alone — every animated signal has a static
equivalent (colour + glyph), so nothing is lost when motion is off.

---

## 7. Token architecture (summary)

Three layers, dark-mode-default. Full definitions in the implementation doc.

```
BASE          raw primitives           --base-cyan-400: #3DE3F0
  ↓           (never used directly in components)
SEMANTIC      meaning-mapped           --color-surface-2, --color-agent-active
  ↓           (dark default, light override)
COMPONENT     component-scoped         --node-ring-active, --hitl-border
```

Components consume **component** or **semantic** tokens only — never base
primitives — so a re-theme touches one layer.

---

*Next: [`factotum-implementation.md`](./factotum-implementation.md) — token values,
CSS variables, Tailwind config, and component build specs.*
