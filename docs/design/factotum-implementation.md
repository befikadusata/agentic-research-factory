# Factotum — Token Architecture & Implementation

> Token values, CSS custom properties, Tailwind v3 wiring, and component build
> notes for the Factotum design language. Rationale and visual intent live in
> [`factotum-design.md`](./factotum-design.md).
>
> **Stack:** Next.js 15 · React 19 · Tailwind CSS 3.4 (`darkMode: "class"`).
> Dark mode is the **default**; light mode is an opt-in `:root.light` override,
> toggled by [`components/ThemeToggle.tsx`](../../frontend/components/ThemeToggle.tsx)
> and applied before first paint by a blocking script in `app/layout.tsx`.
>
> **Status: built.** This shipped as
> [`frontend/app/globals.css`](../../frontend/app/globals.css) and
> [`frontend/tailwind.config.ts`](../../frontend/tailwind.config.ts), which are the
> **source of truth**. The code blocks in §2–§7 are design intent, abridged, and
> have not been re-verified line by line against the shipped files — read them as
> the reasoning behind the tokens, not as the current values. Where the two
> disagree, the CSS wins. §9 records what was built and what is still unbuilt.

---

## 1. Token architecture

Three layers. Components read **semantic** and **component** tokens only — never
base primitives. Re-theming touches semantic/component; the palette lives in base.

```
┌── BASE ────────────────────────────────────────────────┐
│ Raw, context-free primitives. Hex only. No meaning.     │
│   --base-obsidian-900   --base-cyan-400   --base-amber-500
└───────────────────────┬────────────────────────────────┘
                        │ mapped by
┌── SEMANTIC ───────────▼────────────────────────────────┐
│ Meaning in the product. Themeable (dark default/light). │
│   --color-surface-2   --color-agent-active   --text-primary
└───────────────────────┬────────────────────────────────┘
                        │ consumed by
┌── COMPONENT ──────────▼────────────────────────────────┐
│ Component-scoped aliases of semantic tokens.            │
│   --node-ring-active   --hitl-border   --log-caret       │
└─────────────────────────────────────────────────────────┘
```

Naming: `--base-{family}-{weight}` · `--color-*` / `--text-*` / `--motion-*`
(semantic) · `--{component}-{part}-{state}` (component).

---

## 2. Base layer

`app/globals.css`

```css
:root {
  /* ── Obsidian / navy spine ────────────────────────────── */
  --base-obsidian-990: #04060A;
  --base-obsidian-950: #070B11;
  --base-obsidian-900: #0A0F17;
  --base-obsidian-850: #0E141E;
  --base-obsidian-800: #131B27;
  --base-obsidian-750: #19222F;
  --base-obsidian-700: #212C3B;
  --base-obsidian-650: #2B3648;
  --base-obsidian-600: #38465B;

  /* ── Cyan — electric primary ──────────────────────────── */
  --base-cyan-300: #7FF3FB;
  --base-cyan-400: #3DE3F0;
  --base-cyan-500: #14C6D9;
  --base-cyan-600: #0C9DB0;
  --base-cyan-700: #0A7C8C;

  /* ── Violet — agent activity ──────────────────────────── */
  --base-violet-300: #C9B8FF;
  --base-violet-400: #A38BF5;
  --base-violet-500: #8467E8;
  --base-violet-600: #6A4FCB;

  /* ── Amber — HITL / human turn ────────────────────────── */
  --base-amber-300: #F7D9A3;
  --base-amber-400: #E9B25C;
  --base-amber-500: #D6963C;
  --base-amber-600: #B4762A;

  /* ── Cool gray / neutral ──────────────────────────────── */
  --base-gray-050: #E9EEF4;   /* cool off-white */
  --base-gray-100: #D4DCE6;
  --base-gray-200: #B4C0CE;
  --base-gray-300: #93A2B4;
  --base-gray-400: #6F8093;
  --base-gray-500: #556575;
  --base-gray-600: #3E4C5C;

  /* ── Feedback ─────────────────────────────────────────── */
  --base-mint-400: #3FD69A;
  --base-rose-400: #F26478;

  /* ── Agent identity (fixed, muted) ────────────────────── */
  --base-agent-supervisor: #5FC7D4;
  --base-agent-strategist: #A38BF5;
  --base-agent-researcher: #6BA8E0;
  --base-agent-analyst:    #58C6A6;
  --base-agent-reviewer:   #C9A96A;
  --base-agent-writer:     #B58BD0;
  --base-agent-editor:     #7E93C4;
}
```

---

## 3. Semantic layer (dark = default)

```css
:root {
  /* ── Surface hierarchy (5 levels) ─────────────────────── */
  --color-surface-0: var(--base-obsidian-990);  /* canvas        */
  --color-surface-1: var(--base-obsidian-900);  /* panel/chrome  */
  --color-surface-2: var(--base-obsidian-850);  /* card          */
  --color-surface-3: var(--base-obsidian-800);  /* input/hover   */
  --color-surface-4: var(--base-obsidian-750);  /* overlay/menu  */

  --color-border-subtle: var(--base-obsidian-700);
  --color-border-strong: var(--base-obsidian-600);
  --color-border-focus:  var(--base-cyan-400);

  /* ── Text ─────────────────────────────────────────────── */
  --text-primary:   var(--base-gray-050);
  --text-secondary: var(--base-gray-300);
  --text-muted:     var(--base-gray-500);
  --text-inverse:   var(--base-obsidian-950);   /* on cyan/light */
  --text-link:      var(--base-cyan-400);

  /* ── Primary / brand ──────────────────────────────────── */
  --color-primary:       var(--base-cyan-400);
  --color-primary-hover:  var(--base-cyan-300);
  --color-primary-press:  var(--base-cyan-500);
  --color-on-primary:     var(--base-obsidian-950);

  /* ── Agent status states ──────────────────────────────── */
  --color-agent-idle:     var(--base-gray-500);
  --color-agent-active:   var(--base-cyan-400);
  --color-agent-thinking: var(--base-violet-400);   /* generating */
  --color-agent-complete: var(--base-mint-400);
  --color-agent-error:    var(--base-rose-400);
  --color-agent-paused:   var(--base-amber-400);     /* HITL */

  /* ── Feedback palette ─────────────────────────────────── */
  --color-success: var(--base-mint-400);
  --color-error:   var(--base-rose-400);
  --color-warning: var(--base-amber-400);
  --color-info:    var(--base-cyan-400);

  /* ── HITL / human-turn accents ────────────────────────── */
  --color-hitl:       var(--base-amber-400);
  --color-hitl-quiet: var(--base-amber-500);
  --color-hitl-glow:   210 178 92;   /* amber-400 as RGB triplet */

  /* ── Glow triplets (for rgba() composition) ───────────── */
  --rgb-cyan:  61 227 240;
  --rgb-amber: 233 178 92;

  /* ── Elevation ────────────────────────────────────────── */
  --shadow-hairline: inset 0 0 0 1px rgb(56 70 91 / 0.40);
  --glow-active: 0 0 0 1px var(--base-cyan-400),
                 0 0 16px -2px rgb(var(--rgb-cyan) / 0.45);
  --glow-hitl:   0 0 0 1px var(--base-amber-400),
                 0 0 24px -4px rgb(var(--rgb-amber) / 0.35);

  /* ── Radii ────────────────────────────────────────────── */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-pill: 999px;

  /* ── Type ─────────────────────────────────────────────── */
  --font-sans: "Inter", "Plus Jakarta Sans", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "JetBrains Mono", "IBM Plex Mono", ui-monospace, "SFMono-Regular", monospace;
}
```

### 3.1 Light mode (optional override)

Cool off-whites only — no warm white. Applied via `:root.light` (pairs with the
existing `darkMode: "class"` config; add `light` to the html element to opt in).

```css
:root.light {
  --color-surface-0: #EEF2F7;
  --color-surface-1: #F7FAFC;
  --color-surface-2: #FFFFFF;   /* neutral, cool-biased white */
  --color-surface-3: #F1F5F9;
  --color-surface-4: #FFFFFF;

  --color-border-subtle: #D9E1EA;
  --color-border-strong: #C2CDD9;

  --text-primary:   #0E141E;
  --text-secondary: #45566A;
  --text-muted:     #6F8093;
  --text-inverse:   #F7FAFC;

  /* Deepen accents so they hold contrast on light surfaces */
  --color-primary:       var(--base-cyan-600);
  --color-agent-active:  var(--base-cyan-600);
  --color-agent-paused:  var(--base-amber-500);
  --color-hitl:          var(--base-amber-500);

  --shadow-hairline: inset 0 0 0 1px rgb(194 205 217 / 0.7);
}
```

---

## 4. Component layer

Component tokens alias semantics so a component can be re-skinned in isolation.

```css
:root {
  /* Agent node */
  --node-idle-border:     var(--color-agent-idle);
  --node-active-border:   var(--color-agent-active);
  --node-active-fill:     rgb(var(--rgb-cyan) / 0.10);
  --node-active-glow:     var(--glow-active);
  --node-complete-border: var(--color-agent-complete);
  --node-error-border:    var(--color-agent-error);
  --node-paused-border:   var(--color-agent-paused);
  --node-edge-idle:       var(--color-border-strong);
  --node-edge-done:       var(--base-cyan-700);
  --node-edge-dot:        var(--base-cyan-400);

  /* HITL card */
  --hitl-surface:  var(--color-surface-2);
  --hitl-border:   var(--color-hitl);
  --hitl-glow:     var(--glow-hitl);
  --hitl-eyebrow:  var(--color-hitl);
  --hitl-focus:    var(--color-hitl);   /* amber focus ring in HITL */
  --hitl-backdrop: rgb(4 6 10 / 0.55);

  /* Log stream */
  --log-surface:    var(--color-surface-1);
  --log-timestamp:  var(--text-muted);
  --log-caret:      var(--color-primary);
  --log-scanline:   rgb(255 255 255 / 0.03);

  /* Citation pill */
  --cite-surface:  var(--color-surface-3);
  --cite-border:   var(--base-cyan-700);
  --cite-index:    var(--color-primary);
  --cite-broken:   var(--color-error);

  /* Cost widget */
  --cost-text:  var(--text-secondary);
  --cost-glyph: var(--color-primary);
  --cost-warn:  var(--color-warning);
}
```

---

## 5. Motion tokens

```css
:root {
  --motion-instant:    80ms;
  --motion-fast:       140ms;
  --motion-base:       220ms;
  --motion-slow:       400ms;
  --motion-deliberate: 700ms;

  --ease-standard: cubic-bezier(0.2, 0, 0, 1);
  --ease-entrance: cubic-bezier(0.16, 1, 0.3, 1);   /* decelerate */
  --ease-exit:     cubic-bezier(0.4, 0, 1, 1);       /* accelerate */

  --loop-pulse: 1.6s;
  --loop-breath: 2.4s;
  --loop-caret: 1.1s;
  --edge-travel: 900ms;
}

/* ── Keyframes ─────────────────────────────────────────── */
@keyframes ftm-node-pulse {
  0%, 100% { box-shadow: 0 0 0 1px var(--base-cyan-400),
                         0 0 0 0 rgb(var(--rgb-cyan) / 0.55); }
  50%      { box-shadow: 0 0 0 1px var(--base-cyan-400),
                         0 0 18px 3px rgb(var(--rgb-cyan) / 0.35); }
}
@keyframes ftm-hitl-breath {
  0%, 100% { box-shadow: 0 0 0 1px var(--base-amber-400),
                         0 0 14px -2px rgb(var(--rgb-amber) / 0.25); }
  50%      { box-shadow: 0 0 0 1px var(--base-amber-400),
                         0 0 30px -2px rgb(var(--rgb-amber) / 0.45); }
}
@keyframes ftm-edge-dot   { from { offset-distance: 0%; } to { offset-distance: 100%; } }
@keyframes ftm-log-in     { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
@keyframes ftm-caret      { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0; } }
@keyframes ftm-hitl-enter { from { opacity: 0; transform: scale(0.98); } to { opacity: 1; transform: none; } }
@keyframes ftm-node-shake { 0%,100%{transform:translateX(0)} 25%{transform:translateX(-3px)} 75%{transform:translateX(3px)} }

/* ── Reduced motion: kill loops & transitions, keep state ─ */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
  }
  .ftm-scanline { display: none; }
  /* Active node keeps a STATIC cyan ring (state stays legible) */
  .ftm-node[data-state="active"] { box-shadow: var(--glow-active); }
  /* Edge flow becomes a solid filled edge instead of a traveling dot */
  .ftm-edge[data-flowing="true"] { background: var(--base-cyan-400); }
}
```

---

## 6. Tailwind wiring (v3.4)

Map semantic tokens into Tailwind so utilities compose. Colours reference CSS
vars, so dark/light switch automatically. This **replaces** the current ad-hoc
`primary`/`status` block in `tailwind.config.ts` with the semantic system (the
old `status.*` states map onto `agent.*` below).

```ts
// tailwind.config.ts
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          0: "var(--color-surface-0)",
          1: "var(--color-surface-1)",
          2: "var(--color-surface-2)",
          3: "var(--color-surface-3)",
          4: "var(--color-surface-4)",
        },
        border: {
          subtle: "var(--color-border-subtle)",
          strong: "var(--color-border-strong)",
          focus:  "var(--color-border-focus)",
        },
        content: {
          DEFAULT:  "var(--text-primary)",
          secondary:"var(--text-secondary)",
          muted:    "var(--text-muted)",
          inverse:  "var(--text-inverse)",
        },
        primary: { DEFAULT: "var(--color-primary)", hover: "var(--color-primary-hover)", press: "var(--color-primary-press)", on: "var(--color-on-primary)" },
        // Agent status (supersedes old `status.*`)
        agent: {
          idle:     "var(--color-agent-idle)",
          active:   "var(--color-agent-active)",
          thinking: "var(--color-agent-thinking)",
          complete: "var(--color-agent-complete)",
          error:    "var(--color-agent-error)",
          paused:   "var(--color-agent-paused)",
        },
        feedback: {
          success: "var(--color-success)",
          error:   "var(--color-error)",
          warning: "var(--color-warning)",
          info:    "var(--color-info)",
        },
        hitl: "var(--color-hitl)",
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      borderRadius: {
        sm: "var(--radius-sm)", md: "var(--radius-md)", lg: "var(--radius-lg)", pill: "var(--radius-pill)",
      },
      boxShadow: {
        hairline: "var(--shadow-hairline)",
        active:   "var(--glow-active)",
        hitl:     "var(--glow-hitl)",
      },
      transitionTimingFunction: {
        standard: "var(--ease-standard)", entrance: "var(--ease-entrance)", exit: "var(--ease-exit)",
      },
      animation: {
        "node-pulse":  "ftm-node-pulse var(--loop-pulse) var(--ease-standard) infinite",
        "hitl-breath": "ftm-hitl-breath var(--loop-breath) ease-in-out infinite",
        "hitl-enter":  "ftm-hitl-enter var(--motion-slow) var(--ease-entrance)",
        "log-in":      "ftm-log-in var(--motion-fast) var(--ease-entrance)",
        "caret":       "ftm-caret var(--loop-caret) step-end infinite",
        "node-shake":  "ftm-node-shake 320ms var(--ease-standard)",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};
export default config;
```

> **Migration note.** Existing components use `status.*` (`pending`,
> `researching`, `awaiting_hitl`, `writing`, `complete`, `failed`). Map them:
> `pending→agent-idle`, `researching→agent-active`, `awaiting_hitl→agent-paused`,
> `writing→agent-thinking`, `complete→agent-complete`, `failed→agent-error`.
> Keep a thin `status` alias in the config during migration if needed.

### Fonts

Prefer `next/font` over the current Google Fonts `@import` (removes a render-
blocking request and sets the `--font-*` vars used above):

```ts
// app/layout.tsx
import { Inter, JetBrains_Mono } from "next/font/google";
const sans = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });
// <html className={`${sans.variable} ${mono.variable}`}>
```

---

## 7. Component build specs

React 19 + Tailwind. Each component reads `data-state` and lets tokens do the work.

### 7.1 Agent node

```tsx
type AgentState = "idle" | "active" | "complete" | "error" | "paused";

const STATE = {
  idle:     "border-agent-idle text-content-muted",
  active:   "border-agent-active text-content bg-primary/10 animate-node-pulse",
  complete: "border-agent-complete text-agent-complete",
  error:    "border-agent-error text-agent-error animate-node-shake",
  paused:   "border-agent-paused text-agent-paused animate-hitl-breath",
} satisfies Record<AgentState, string>;

export function AgentNode({ agent, state, icon: Icon }: {
  agent: string; state: AgentState; icon: React.ComponentType<{ className?: string }>;
}) {
  const glyph = { complete: "✓", error: "✕", paused: "▮▮" }[state as string];
  return (
    <div
      data-state={state}
      className={`ftm-node flex flex-col items-center gap-1.5 rounded-md border
                  px-4 py-3 min-w-[104px] transition-colors duration-base
                  ease-standard bg-surface-2 ${STATE[state]}`}
      role="listitem"
      aria-label={`${agent}: ${state}`}
    >
      <span className="relative text-lg leading-none">
        {glyph ?? <Icon className="h-4 w-4" />}
      </span>
      <span className="text-[11px] font-medium tracking-wide">{agent}</span>
    </div>
  );
}
```

**Edge with traveling dot** — CSS `offset-path` on the connector so the dot rides
the line; falls back to a solid fill under reduced motion (§5).

```css
.ftm-edge { position: relative; height: 1px; background: var(--node-edge-idle); flex: 1; }
.ftm-edge[data-flowing="true"]::after {
  content: ""; position: absolute; inset: 0; margin: auto; width: 5px; height: 5px;
  border-radius: 999px; background: var(--node-edge-dot);
  box-shadow: 0 0 8px 1px rgb(var(--rgb-cyan) / 0.6);
  offset-path: path("M0,0 H400");            /* set to real edge length */
  animation: ftm-edge-dot var(--edge-travel) linear infinite;
}
.ftm-edge[data-done="true"] { background: var(--node-edge-done); }
```

### 7.2 Pipeline progress bar (compact variant)

Segmented, one segment per agent; active segment carries the pulse, paused turns
amber. Share the `AgentState` model with the node so both stay in sync.

```tsx
<div className="flex gap-1" role="progressbar" aria-valuenow={done} aria-valuemax={total}>
  {agents.map((a) => (
    <span key={a.id} data-state={a.state}
      className={`h-1.5 flex-1 rounded-pill transition-colors duration-base
        ${a.state === "complete" ? "bg-agent-complete"
        : a.state === "active"   ? "bg-agent-active animate-node-pulse"
        : a.state === "paused"   ? "bg-agent-paused animate-hitl-breath"
        : a.state === "error"    ? "bg-agent-error"
        : "bg-surface-3"}`} />
  ))}
</div>
```

### 7.3 HITL checkpoint card

The pipeline dims behind (`--hitl-backdrop`); this card is the only lit surface.
Amber border + glow + amber focus ring on the textarea. Cyan `Continue run →`.

```tsx
export function HitlCheckpoint({ draft, onContinue, onDiscard }: {
  draft: string; onContinue: (note: string) => void; onDiscard: () => void;
}) {
  const [note, setNote] = React.useState("");
  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-6"
         style={{ background: "var(--hitl-backdrop)" }}>
      <section
        className="ftm-hitl w-full max-w-xl rounded-lg bg-surface-2 p-6
                   animate-hitl-enter shadow-hitl"
        role="alertdialog" aria-modal="true" aria-label="Checkpoint — your review needed"
      >
        <header className="mb-4 flex items-center gap-2 border-b border-hitl/30 pb-3">
          <span className="text-hitl" aria-hidden>▮▮</span>
          <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-hitl">
            Checkpoint · your review needed
          </span>
        </header>

        <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-content-muted">
          Draft summary
        </p>
        <div className="mb-5 max-h-48 overflow-auto rounded-md bg-surface-3 p-3
                        text-[13px] leading-relaxed text-content-secondary">
          {draft}
        </div>

        <label htmlFor="hitl-note"
          className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-content-muted">
          Corrections (optional)
        </label>
        <textarea id="hitl-note" value={note} onChange={(e) => setNote(e.target.value)}
          rows={3} placeholder="Tighten the pricing section, add a SOC2 note…"
          className="mb-6 w-full resize-none rounded-md bg-surface-3 p-3 text-[13px]
                     text-content placeholder:text-content-muted outline-none
                     ring-1 ring-border-subtle focus:ring-2 focus:ring-hitl" />

        <div className="flex justify-end gap-3">
          <button onClick={onDiscard}
            className="rounded-md px-4 py-2 text-[13px] text-content-secondary
                       hover:bg-surface-3 transition-colors">
            Discard
          </button>
          <button onClick={() => onContinue(note)}
            className="rounded-md bg-primary px-4 py-2 text-[13px] font-semibold
                       text-primary-on hover:bg-primary-hover transition-colors
                       focus:outline-none focus:ring-2 focus:ring-border-focus focus:ring-offset-2
                       focus:ring-offset-surface-2">
            Continue run →
          </button>
        </div>
      </section>
    </div>
  );
}
```

> While this card is open, **freeze pipeline motion**: set a `data-paused="true"`
> on the pipeline root and gate the pulse/edge animations off in CSS
> (`[data-paused="true"] .ftm-node { animation: none; }`). Stillness is the point.

### 7.4 Log stream

Monospace feed, fixed-width agent-hue prefix column, streaming line-in, live
caret, scanline overlay. Virtualize for long runs; auto-scroll pins to bottom.

```tsx
const AGENT_HUE: Record<string, string> = {
  supervisor: "var(--base-agent-supervisor)", strategist: "var(--base-agent-strategist)",
  researcher: "var(--base-agent-researcher)", analyst: "var(--base-agent-analyst)",
  reviewer: "var(--base-agent-reviewer)", writer: "var(--base-agent-writer)",
  editor: "var(--base-agent-editor)",
};

export function LogStream({ lines, live }: { lines: LogLine[]; live: boolean }) {
  return (
    <div className="ftm-scanline relative overflow-auto rounded-lg bg-surface-1
                    p-3 font-mono text-[13px] leading-[1.5]"
         role="log" aria-live="polite">
      {lines.map((l) => (
        <div key={l.id} className="ftm-log-line flex gap-3 animate-log-in">
          <time className="shrink-0 text-content-muted tabular-nums">{l.ts}</time>
          <span className="w-24 shrink-0 font-semibold" style={{ color: AGENT_HUE[l.agent] }}>
            {l.agent}
          </span>
          <span className="text-content-secondary">{l.text}</span>
        </div>
      ))}
      {live && <span className="ml-[6.75rem] inline-block h-4 w-2 bg-[var(--log-caret)] animate-caret" />}
    </div>
  );
}
```

```css
/* scanline overlay — texture only, never animated */
.ftm-scanline::before {
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background: repeating-linear-gradient(
    to bottom, transparent 0 1px, var(--log-scanline) 1px 2px);
}
```

### 7.5 Playbook selector

```tsx
export function PlaybookCard({ title, blurb, agents, glyph, selected, onSelect }: {
  title: string; blurb: string; agents: number; glyph: React.ReactNode;
  selected: boolean; onSelect: () => void;
}) {
  return (
    <button onClick={onSelect} aria-pressed={selected}
      className={`group flex flex-col gap-2 rounded-lg border p-4 text-left
        transition-all duration-base ease-standard
        ${selected
          ? "border-agent-active bg-surface-2 shadow-active"
          : "border-border-subtle bg-surface-2 hover:-translate-y-0.5 hover:bg-surface-3"}`}>
      <span className="text-xl text-primary">{glyph}</span>
      <span className="text-[15px] font-semibold text-content">{title}</span>
      <span className="text-[13px] text-content-secondary">{blurb}</span>
      <span className="mt-2 font-mono text-[11px] text-content-muted">~{agents} agents</span>
      {selected && <span className="absolute right-3 top-3 text-agent-active">✓</span>}
    </button>
  );
}
```

### 7.6 Citation pill

```tsx
export function Citation({ index, source, locator, broken }: {
  index: number; source: string; locator?: string; broken?: boolean;
}) {
  return (
    <button className="inline-flex items-center gap-1.5 rounded-pill border
                       border-[var(--cite-border)] bg-surface-3 px-2 py-0.5
                       font-mono text-[11px] align-baseline">
      <span className={`grid h-4 w-4 place-items-center rounded-full text-[10px]
        ${broken ? "bg-feedback-error text-content-inverse" : "bg-primary/15 text-primary"}`}>
        {index}
      </span>
      <span className="text-content-secondary">{source}</span>
      {locator && <span className="text-content-muted">· {locator}</span>}
    </button>
  );
}
```

### 7.7 Cost micro-widget

```tsx
export function CostWidget({ tokens, cost, overBudget }: {
  tokens: number; cost: number; overBudget?: boolean;
}) {
  return (
    <span className={`inline-flex items-center gap-1.5 font-mono text-[12px]
      ${overBudget ? "text-feedback-warning" : "text-content-secondary"}`}>
      <span className="text-[var(--cost-glyph)]" aria-hidden>⌁</span>
      {(tokens / 1000).toFixed(1)}k tok · ${cost.toFixed(3)}
    </span>
  );
}
```

### 7.8 Tenant workspace switcher

```tsx
const ROLE = { viewer: "text-content-muted", operator: "text-primary", admin: "text-agent-thinking" };

export function TenantSwitcher({ current, role }: { current: { name: string; monogram: string }; role: keyof typeof ROLE }) {
  return (
    <button className="inline-flex items-center gap-2 rounded-md bg-surface-2
                       px-2.5 py-1.5 text-[13px] hover:bg-surface-3 transition-colors">
      <span className="grid h-6 w-6 place-items-center rounded-sm bg-surface-4
                       font-mono text-[11px] text-content-secondary">
        {current.monogram}
      </span>
      <span className="text-content">{current.name}</span>
      <span className={`font-mono text-[10px] uppercase ${ROLE[role]}`}>{role}</span>
      <span className="text-content-muted" aria-hidden>▾</span>
    </button>
  );
}
```

---

## 8. State → token cheat sheet

| Run/agent state | Border / accent | Fill | Glyph | Motion (full → reduced) |
| --- | --- | --- | --- | --- |
| idle | `agent-idle` | none | — | none |
| active | `agent-active` (cyan) | `primary/10` | agent icon | pulse ring → static ring |
| thinking | `agent-thinking` (violet) | `agent-thinking/10` | ◐ | subtle → none |
| complete | `agent-complete` (mint) | `agent-complete/12` | ✓ | none |
| error | `agent-error` (rose) | `agent-error/12` | ✕ | one-shot shake → none |
| paused-hitl | `agent-paused` (amber) | `agent-paused/12` | ▮▮ | breath → static ring |

---

## 9. Implementation checklist

- [x] Add base + semantic + component + motion tokens to `app/globals.css`.
- [x] Replace the `colors`/`fontFamily` block in `tailwind.config.ts` (§6).
      (Old `status.*` block removed outright rather than aliased — every
      call site was migrated to `agent.*`/`statusBadgeClass()` in the same
      pass, so no transitional alias was needed.)
- [x] Swap Google-Fonts `@import` for `next/font` (Inter + JetBrains Mono),
      wiring `--font-sans` / `--font-mono`.
- [~] Build components 7.1–7.8 against semantic/component tokens only.
      Done for the specs with a real counterpart in this app: 7.1 Agent
      node → `AgentGraph.tsx`, 7.2 Pipeline progress bar →
      `PipelineProgress.tsx` (wired into `RunCard.tsx` on the dashboard;
      node-state derivation shared with `AgentGraph.tsx` via the new
      `pipelineNodeState()` helper in `lib/types.ts`), 7.3 HITL checkpoint
      → `HitlModal.tsx`, 7.4 Log stream → `AgentLog.tsx`, 7.5 Playbook
      selector → `VerticalSelector.tsx`/`FormatSelector.tsx`. 7.6
      (citation pill), 7.7 (cost widget), 7.8 (tenant switcher) have no
      existing component to retrofit — not built, not needed yet.

      Note found while visually verifying 7.2 (Playwright screenshot
      across all run statuses), since fixed: for `status: "failed"` runs,
      every segment rendered idle instead of marking the failure point,
      because `RUN_STATUS_MAP.failed = -1` and `pipelineNodeState`'s
      `idx <= activeIdx` check could never be true — a pre-existing quirk
      inherited unchanged from `AgentGraph.tsx`. Root cause: the backend
      `Run` model only ever stored the terminal `status`, with no record
      of which stage was active at the moment of failure. Fixed with a
      new `runs.failed_at_status` column (migration
      `15fd6ff9382d_add_failed_at_status_to_runs`, reusing the existing
      `runstatus` Postgres enum type), populated in
      `run_service._set_status()` by capturing the run's current status
      right before it's overwritten to `failed`. Exposed on
      `RunResponse`/`RunDetailResponse` (so both the dashboard list and
      the run-detail page get it), threaded through
      `pipelineNodeState(status, nodeId, failedAtStatus)` and both call
      sites (`RunCard`/`PipelineProgress`, `app/runs/[id]/page.tsx`/
      `AgentGraph`). The run-detail page also re-fetches the run on the
      SSE `error` event (mirroring what it already did on `complete`),
      since the backend commits `failed_at_status` before emitting that
      event — so a run watched failing live shows the correct node
      without needing a reload. Runs that failed before this migration
      (`failed_at_status` still `null`) fall back to the old all-idle
      rendering rather than guessing. Covered by
      `test_set_status_records_stage_a_run_failed_at`,
      `test_set_status_failed_twice_keeps_first_failure_stage`, and
      `test_run_detail_exposes_failed_at_status` in
      `backend/tests/test_runs.py`; verified visually via Playwright
      screenshots of both the dashboard list and the run-detail graph.
- [x] Verify contrast: primary text ≥ 7:1, secondary ≥ 4.5:1 on every surface.
      Computed WCAG ratios for every text/surface pair. `text-primary`
      (14.8–17.4:1) and `text-secondary` (6.65–7.79:1) clear their targets
      everywhere. Found two failures and fixed by promoting the affected
      tokens from `gray-500` to `gray-400`: `text-muted` (was 2.9–3.4:1,
      now 4.27–5.01:1 — used for real content like log timestamps, not
      decorative) and `agent-idle` badge text (was 3.20:1, now 4.74:1).
      Light-mode surfaces re-checked too; light `text-muted` bumped from
      `gray-400` to `gray-500` (was 3.6–4.05:1, now 5.33–5.99:1). The
      light-mode `agent-thinking`/`agent-complete`/`agent-error` hues are
      not used as real text — `AGENT_STATE_BADGE` and the run-detail
      banners render neutral `text-content` with the hue only as a `/10`
      tint + `/40` border (decorative, colour never the sole signal), so
      their sub-4.5:1 measurement never applied to readable text.

      One genuine light-mode gap remained and is now fixed:
      `--color-primary` (cyan) is *real* text via `text-primary` (nav link,
      "Create your first run" link, the required-field asterisk) and it
      measured only 2.89–3.25:1 on light surfaces — and light mode never
      overrode `--color-primary-hover`/`-press`, so link/button hover fell
      back to the dark-mode `cyan-300` (#7FF3FB), near-invisible on white.
      Fixed at the semantic layer: added base cyan-800/850/900 dark-teal
      shades and re-pointed light `--color-primary`/`-hover`/`-press` to
      them, flipping light `--color-on-primary` to white so button labels
      still read on the darkened fill (a dark obsidian label would fail on
      it). Measured in a real browser engine (Playwright, reading the
      computed cascade with `.light` applied): link on surface-0 4.92:1
      (was 2.89:1), button label-on-fill 5.28:1, hover 6.42:1; dark mode
      unchanged at 12.98:1.
- [x] Confirm every status has a non-colour glyph (colour-blind safe).
      `AGENT_STATE_GLYPH` in `lib/types.ts` (◐ ✓ ✕ ▮▮), verified live via
      Playwright screenshots.
- [x] Test full `prefers-reduced-motion` path — state must stay legible with
      all loops/scanline/caret off. Verified via Playwright's
      `reducedMotion: 'reduce'` emulation.
- [x] Add a `.light` opt-in and re-check contrast on light surfaces.
      Added a real toggle (`components/ThemeToggle.tsx`, in the sidebar)
      that flips a `light` class on `<html>` and persists it via
      `localStorage`, plus a blocking inline script in `layout.tsx` to set
      it before first paint (no flash of the wrong theme).

      Re-checking surfaced a deeper bug than a missing override: Tailwind's
      `agent.*`/`feedback.*`/`primary`/`hitl` colors all resolve through the
      `--rgb-cyan`/`--rgb-violet`/`--rgb-mint`/`--rgb-rose`/`--rgb-amber`
      triples (required for opacity modifiers), not the `--color-*`
      semantic aliases — so the `:root.light` overrides on `--color-primary`
      /`--color-agent-active`/`--color-agent-paused`/`--color-hitl` were
      dead code for every Tailwind utility class; they only ever reached
      the component-layer tokens (`--node-*-border`, `--hitl-*`,
      `--log-caret`, `--cite-*`, `--cost-*`) that reference them directly.
      Fixed by overriding the `--rgb-*` triples themselves inside
      `:root.light`, using new `--base-mint-600`/`--base-rose-600` (added;
      only a `-400` existed before) plus the existing `-600` cyan/violet/
      amber shades.

      Also found while re-checking: even the *deepened* shades the original
      spec's `:root.light` block picked (cyan-600, amber-500) don't clear
      4.5:1 as text on white (measured 3.25:1 / 2.53:1) — they only clear
      the 3:1 non-text/border minimum. So every place a hue was used as
      real (non-decorative) text — `AGENT_STATE_BADGE`, HITL/error/resuming
      banners, the HITL eyebrow label — now uses neutral `text-content`
      instead, with the hue kept for the background tint, border, and
      decorative glyphs (state is still never color-only: badges also
      carry the glyph from `AGENT_STATE_GLYPH`). Bumped `agent-paused`/
      `hitl` from amber-500 to amber-600 for the border/glyph case (was
      2.53:1, fails even 3:1).

      Bonus fix found along the way: `bg-agent-idle/15` was silently
      generating no CSS at all (Tailwind can't apply an opacity modifier to
      a plain `var(--color-agent-idle)` hex string) — added `--rgb-gray-400`
      and pointed `agent.idle` at it so the idle/pending badge tint
      actually renders.

      Verified live in both themes via Playwright (toggle click + full-page
      screenshots): sign-in page and a component harness covering all 6
      status badges, the HITL card, and the agent log. No console errors.

      **Follow-up items found above are now fixed too:**
      (1) `VERTICALS[].accentClass` moved off raw Tailwind defaults
      (`text-violet-400 bg-violet-950/40`) onto a new `category.{sales,
      competitor,strategy}` Tailwind color group backed by the same
      light-mode-aware `--rgb-*` triples (added `--rgb-blue`/`--base-blue-
      400/600` since no blue existed in the palette), with the tag text
      switched to neutral `text-content` the same way the state badges
      were; (2) `AGENT_COLORS` in `AgentLog.tsx` reads `--base-agent-*`
      directly (by design, no Tailwind opacity use), so those seven base
      values got direct `:root.light` overrides deepened to clear 4.5:1 on
      white (dark-mode originals measured 1.98–3.06:1); (3) `OutputPanel.tsx`
      and `HitlModal.tsx` both hardcoded `prose-invert` regardless of
      theme — added `lib/useTheme.ts` (`useIsLightMode`, a `MutationObserver`
      on `<html>`'s class list) so both now pick `prose` vs `prose-invert`
      live. All three re-verified via the same Playwright toggle-and-
      screenshot harness in both themes.

---

*See [`factotum-design.md`](./factotum-design.md) for visual rationale and
component intent.*
