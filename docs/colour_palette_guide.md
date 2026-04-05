# Colour Palette Guide

## 1. Dark base — a single shared hue family

All background and surface tones share the same blue-purple hue (~230°) at near-zero saturation. Depth is created purely by lightness:

| Token | Value | Role |
|---|---|---|
| `--icell-bg` | `#0f0f13` | Page canvas |
| `--icell-bg-alt` | `#141420` | Secondary background |
| `--icell-panel` | `rgba(20,20,28,0.96)` | Floating panels |
| `--icell-surface` | `rgba(14,14,20,0.95)` | Recessed surfaces |
| `--icell-border` | `rgba(255,255,255,0.07)` | Subtle dividers |
| `--icell-border-strong` | `rgba(255,255,255,0.18)` | Prominent dividers |

Using the same underlying hue family (rather than pure black `#000`) keeps every shade warm and cohesive. Transparency on panels lets backgrounds bleed through, adding free depth.

---

## 2. Text hierarchy — three luminance stops

```
--icell-text       #ebebf2   ← primary copy
--icell-text-muted #ababc0   ← secondary / labels
--icell-text-dim   #8888a8   ← tertiary / kickers
```

All three are desaturated versions of the same hue. The jump in lightness (~93 → 67 → 53%) creates clear hierarchy without introducing separate hues.

---

## 3. Single accent colour + derived tints

```
--icell-accent        #818cf8   (indigo-400)
--icell-accent-strong #4f46e5   (indigo-600)
--icell-accent-soft   rgba(129,140,248,0.10)
```

One accent hue (indigo) is used for every interactive element. Tints are derived by opacity, not mixing new colours. Focus rings use `rgba(129,140,248,0.08/0.5)` — the same hue at low opacity — so they feel native rather than jarring.

---

## 4. Semantic status colours

```
--icell-danger   #f87171   (red-400)
--icell-warning  #fbbf24   (amber-400)
--icell-success  #4ade80   (green-400)
```

These come directly from the Tailwind 400-step palette. 400-steps are chosen deliberately: bright enough to read on dark backgrounds but not so saturated they feel alarming. Status banners pair a 12% opacity background fill with a 35% opacity border in the same hue, using `rgba()` tints rather than a second colour.

---

## 5. Well/compound colours — golden-angle HSL generation

Compound fill colours and concentration ring colours are generated at runtime using the **golden angle (≈137.508°)** as the hue step:

```ts
// Compound fills — rich, mid-depth
function groupHsl(index: number): string {
  const hue = (215 + index * 137.508) % 360;
  return `hsl(${hue.toFixed(1)}, 68%, 48%)`;
}

// Concentration rings — bright, electric
function concHsl(index: number): string {
  const hue = (35 + index * 137.508) % 360;
  return `hsl(${hue.toFixed(1)}, 90%, 68%)`;
}
```

**Why this works:**
- The golden angle is irrational, so successive hues never cluster — any N compounds span the wheel as evenly as possible.
- The two palettes use different anchor hues (215° vs 35°) and different saturation/lightness (68%/48% vs 90%/68%), so fills and rings are always visually distinct from each other.
- Fixed static colours handle edge cases: `CONTROL_COLOR = hsl(225,15%,35%)` (desaturated, recedes) and `EMPTY_COLOR = hsl(230,18%,18%)` (near-invisible, matches background).

---

## 6. Typography

```css
font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
/* monospaced values */
font-family: "IBM Plex Mono", monospace;
```

IBM Plex Sans paired with IBM Plex Mono keeps the scientific/lab aesthetic. Kicker labels use `letter-spacing: 0.16–0.18em` + `text-transform: uppercase` at `0.74–0.76rem` to separate metadata from headings without bold weight.

---

## Summary of the system

```
Background family  → single hue (~230°), vary only lightness
Text               → same hue, three luminance stops
Accent             → one indigo, three opacity tints
Status             → Tailwind 400 steps, tint-fill + tint-border
Plate colours      → golden-angle HSL, two independent palettes
```

No random colour picks. Every value is either a predictable step in a shared hue family or a mathematically distributed golden-angle hue.
