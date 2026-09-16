---
name: buildless-react-frontend
description: Scaffold or reshape a frontend as a build-tool-free React shell — React and Lucide icons loaded via ESM CDN with zero bundler, served by a thin backend proxy, styled through one CSS design-token stylesheet. Use when starting a new frontend, when the user asks for "no build step" / "no bundler" / "no Vite/Webpack/Next.js" UI, or when asked to replicate the Cloudera Workforce Intelligence frontend stack in another project.
---

# Buildless React Frontend

Build the frontend using this exact stack — no bundler, no build step.

## Runtime & serving

A thin backend app (FastAPI, or the equivalent lightweight framework for
whatever backend language the project already uses) serves static files
(`index.html`, `styles.css`, `app.js`) and proxies all API calls to the
real backend under one path prefix (e.g. `/api-proxy/{path}` -> backend),
so the browser only ever talks to one origin. This avoids CORS entirely
and keeps deployment to a single process.

## UI library — loaded via CDN, zero build step

React 18.3.1 as an ES Module straight from esm.sh, imported directly in a
`<script type="module">` or a plain `.js` file:

```js
import React from "https://esm.sh/react@18.3.1";
import { createRoot } from "https://esm.sh/react-dom@18.3.1/client";
```

No Vite, Webpack, Next.js, or Create React App. No `node_modules`, no
`package.json` for the frontend. The browser resolves the imports at
request time via the CDN.

## Icons — Lucide, named imports only, no raw inline SVG

```js
import {
  ArrowRight, ArrowUpRight, BadgeCheck, BadgeDollarSign, Bell,
  BookOpenCheck, Briefcase, BriefcaseBusiness, ChartPie, ChevronDown,
  CircleAlert, CloudUpload, Contact, Copy, Database, Download,
  ExternalLink, EyeOff, FileUser, Files, FlaskConical, Gauge, House,
  Info, Layers3, LockKeyhole, Menu, MessageSquarePlus, RotateCcw,
  ScanSearch, Search, Send, Settings, ShieldCheck, SlidersHorizontal,
  Target, ThumbsDown, ThumbsUp, Upload, UserPlus, Users, Workflow, X,
} from "https://esm.sh/lucide-react@0.468.0?deps=react@18.3.1";
```

Import only the icons the project actually needs — the list above is a
reference set from a real app, not a mandatory import list. Wrap whatever
subset is used in one lookup map (e.g. `icons["search"] = Search`) so the
rest of the app references icons by string key instead of importing each
one individually at every call site.

Use only functional/enterprise icons (search, users, briefcase, shield,
database, upload, chart, settings, bell, etc.) — never decorative
sparkle/magic-wand/AI-motif icons unless the product is explicitly
playful/consumer-facing.

Keep icon sizing consistent across the whole app via fixed presets, not
ad hoc per-instance sizes:

- `size: 20, strokeWidth: 1.75` — default/body icons
- `size: 16, strokeWidth: 2` — small/inline icons (buttons, badges, list rows)
- `size: 24, strokeWidth: 1.5` — large icons (empty states, section headers)

## Styling — one CSS file, CSS custom properties as the design system

No Tailwind, no CSS-in-JS, no component library. A single `styles.css`
with a `:root` block defining every color/spacing/radius token:

```css
:root {
  --ink: #12005e;       /* headings, primary text */
  --muted: #5b5a75;
  --line: #e6e4ee;
  --surface: #ffffff;
  --canvas: #f7f6fb;
  --accent: #f96702;    /* primary CTA / emphasis */
  --accent-soft: #fff1e8;
  --secondary: #514ef5; /* selection/active state */
  --secondary-soft: #edecfe;
  --green: #168a50;  --green-soft: #eaf7ef;   /* success */
  --amber: #b45f06;  --amber-soft: #fff6e7;   /* warning/review */
  --radius: 12px;
}
```

Swap the actual hex values for whatever brand palette the project needs
— the token *names* and the "everything reads from `:root`, nothing is a
bare hex outside it" rule are what makes this reusable and rebrand-safe.

Rules to apply:

- Every component styles itself off these tokens — never a hardcoded hex
  anywhere outside `:root` (and its `prefers-color-scheme`/`[data-theme]`
  overrides, if the project supports theming).
- Responsive grids use `minmax(0, ...)` inside `grid-template-columns`
  instead of bare `1fr`/`auto`. Bare tracks carry an implicit
  `min-width: auto`, which blocks the track from shrinking below its
  content's natural width and is the single most common cause of
  horizontal overflow at high browser zoom or narrow viewports.
- Prefer `clamp()` for fluid gaps/padding, and
  `repeat(auto-fit, minmax(...))` for self-wrapping card grids, over
  fixed column-count breakpoints that need separate overrides per
  viewport width.
- Flat surfaces, thin 1px borders using the `--line` token, minimal
  shadow (e.g. `0 1px 2px rgba(0,0,0,.05)`) — no gradients, no
  glassmorphism, no heavy shadows.

## State management

Plain JS/React state (`useState`, a module-level state object) — no
Redux, no MobX, no global state library, unless the project's actual
complexity already justifies one. Don't add one preemptively.

## Why this stack

- Zero build step means zero build tooling to maintain, debug, or keep
  in sync across environments — the whole frontend is just static files
  a thin backend serves as-is.
- CDN-loaded React/Lucide keeps the deployed artifact tiny and avoids a
  `node_modules` dependency tree in backend-oriented deployment
  environments (PaaS platforms, single-container deploys, or anywhere
  shipping one process beats maintaining a separate Node build
  pipeline).
- One CSS token file as the design system makes global rebrands (color
  hierarchy changes, dark mode, new brand palette) a single-file edit
  instead of a hunt through scattered component styles.

## When NOT to use this

If the project already has an established frontend build pipeline
(Next.js, Vite, an existing component library), or needs SSR/SSG,
code-splitting, or a large component ecosystem (design system libraries,
complex forms), this buildless approach fights the project's actual
needs — use the project's existing stack instead.
