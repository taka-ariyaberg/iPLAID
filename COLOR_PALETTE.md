# iCELL Colour Palette Guide

## Two Distinct Palettes

**Cell groups** — cool palette (blues, cyans, greens):
```ts
const GROUP_COLOR_PALETTE = [
  '#00d9ff', '#ff6b9d', '#ffd700',
  '#00ff88', '#ff8c42', '#00b8ff',
  '#ff66cc', '#66ff66', '#ffaa33',
  '#33aaff', '#ff3366', '#aaff33'
];
```

**Dye programs** — warm palette (oranges, pinks, purples), deliberately avoids blues/cyans:
```ts
const DYE_PALETTE = [
  '#ff6b35', '#f72585', '#ffbe0b', '#ff4d6d',
  '#c77dff', '#80ed99', '#ff9f1c', '#e040fb',
  '#f4a261', '#ff595e', '#b5e48c', '#ff70a6',
];
```

## Collision-Avoiding Assignment (`generateDistinctColors`)

1. Sort group names alphabetically for stable ordering.
2. Hash the name (`djb2` variant) → preferred palette index.
3. If that index is taken, walk forward through the palette until a free slot is found.
4. Overflow (more groups than colours): fall back to `orderIndex % palette.length`.

This guarantees no two groups share a colour unless the palette is exhausted, and keeps assignments stable across renders.

## Hash Function

```ts
function hashName(name: string): number {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = ((hash << 5) - hash) + name.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}
```

## Dye Mode Visual Rules

| Well state | Colour |
|---|---|
| Has dye | `dyeProgramColors[dye]` |
| No dye, has group | `groupColors[group] + '44'` (27 % opacity — dimmed) |
| Empty | `#1a1a2e` (dark background) |

## Selection Glow

Selected wells get an inset + outer `box-shadow` using their own colour:
```ts
`inset 0 0 8px ${glowColor}, 0 0 12px ${glowColor}`
```

## Export Consistency

`exportUtils.ts` duplicates both palettes and uses the same collision-avoidance logic so SVG exports match the UI exactly. Keep the two files in sync whenever changing a palette.
