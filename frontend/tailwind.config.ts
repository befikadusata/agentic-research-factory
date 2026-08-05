import type { Config } from "tailwindcss";
import typography from "@tailwindcss/typography";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
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
          focus: "var(--color-border-focus)",
        },
        content: {
          DEFAULT: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          muted: "var(--text-muted)",
          inverse: "var(--text-inverse)",
        },
        // rgb(var(--rgb-x) / <alpha-value>) lets Tailwind's opacity
        // modifiers (bg-primary/10, border-hitl/30, …) work — a plain
        // var(--color-x) hex string can't be combined with a /NN suffix.
        primary: {
          DEFAULT: "rgb(var(--rgb-cyan) / <alpha-value>)",
          hover: "var(--color-primary-hover)",
          press: "var(--color-primary-press)",
          on: "var(--color-on-primary)",
        },
        // Agent status — supersedes the old `status.*` map:
        // pending→idle, researching→active, awaiting_hitl→paused,
        // writing→thinking, complete→complete, failed→error.
        agent: {
          idle: "rgb(var(--rgb-gray-400) / <alpha-value>)",
          active: "rgb(var(--rgb-cyan) / <alpha-value>)",
          thinking: "rgb(var(--rgb-violet) / <alpha-value>)",
          complete: "rgb(var(--rgb-mint) / <alpha-value>)",
          error: "rgb(var(--rgb-rose) / <alpha-value>)",
          paused: "rgb(var(--rgb-amber) / <alpha-value>)",
        },
        feedback: {
          success: "rgb(var(--rgb-mint) / <alpha-value>)",
          error: "rgb(var(--rgb-rose) / <alpha-value>)",
          warning: "rgb(var(--rgb-amber) / <alpha-value>)",
          info: "rgb(var(--rgb-cyan) / <alpha-value>)",
        },
        hitl: "rgb(var(--rgb-amber) / <alpha-value>)",
        // Vertical/category accent tags (reuses agent-state hues so they
        // stay light-mode-aware automatically via the same --rgb-* triples).
        category: {
          sales: "rgb(var(--rgb-violet) / <alpha-value>)",
          competitor: "rgb(var(--rgb-blue) / <alpha-value>)",
          strategy: "rgb(var(--rgb-mint) / <alpha-value>)",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        pill: "var(--radius-pill)",
      },
      boxShadow: {
        hairline: "var(--shadow-hairline)",
        active: "var(--glow-active)",
        hitl: "var(--glow-hitl)",
      },
      transitionTimingFunction: {
        standard: "var(--ease-standard)",
        entrance: "var(--ease-entrance)",
        exit: "var(--ease-exit)",
      },
      transitionDuration: {
        instant: "var(--motion-instant)",
        fast: "var(--motion-fast)",
        base: "var(--motion-base)",
        slow: "var(--motion-slow)",
        deliberate: "var(--motion-deliberate)",
      },
      animation: {
        "node-pulse": "ftm-node-pulse var(--loop-pulse) var(--ease-standard) infinite",
        "hitl-breath": "ftm-hitl-breath var(--loop-breath) ease-in-out infinite",
        "hitl-enter": "ftm-hitl-enter var(--motion-slow) var(--ease-entrance)",
        "log-in": "ftm-log-in var(--motion-fast) var(--ease-entrance)",
        caret: "ftm-caret var(--loop-caret) step-end infinite",
        "node-shake": "ftm-node-shake 320ms var(--ease-standard)",
      },
    },
  },
  plugins: [typography],
};

export default config;
