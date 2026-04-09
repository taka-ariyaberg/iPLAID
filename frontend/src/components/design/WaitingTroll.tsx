/**
 * WaitingTroll — purely cosmetic module.
 *
 * Exports:
 *   useWaitingTroll(active, assignments, allUsableKeys, onComplete?)
 *     Hook that maintains tokens only for assigned (coloured) wells.
 *     A burst every ~700 ms redistributes ALL assigned tokens to new
 *     distinct positions drawn from the full usable-well pool, so tokens
 *     travel freely across empty positions.  Emits { tokens, progress }.
 *
 *   TrollOverlay
 *     Renders absolutely-positioned coloured discs inside the grid-wrapper that
 *     physically travel between well positions, gliding with ease-in-out.
 *     Moving tokens are raised to z-index 10 so they pass over well cells.
 *
 *   TrollProgressBar
 *     Thin progress bar rendered below the grid.
 */

import React, { useEffect, useRef, useState } from "react";
import "./WaitingTroll.css";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface WellAssignment {
  key: string;   // "row,col"
  color: string;
}

export interface TrollToken {
  id: number;    // stable identity = original index
  key: string;   // current well position
  color: string;
}

// ---------------------------------------------------------------------------
// Pixel helpers
// ---------------------------------------------------------------------------

/**
 * Convert a "row,col" key to the pixel top-left of the well inside the
 * grid-wrapper.  The overlay has position:absolute;inset:0 inside the
 * wrapper, so its origin is the wrapper's inner border edge.  From there:
 *   • 8px  = wrapper padding (padding: 8px on .design-plate-grid-wrapper)
 *   • 12px = grid padding   (padding: 12px on .design-plate-grid)
 * Grid tracks then follow: [headerSize] [gap] [wellSize] [gap] …
 */
const GRID_PAD = 20; // 8px wrapper-padding + 12px grid-padding

function wellTopLeft(
  key: string,
  wellSize: number,
  gap: number,
  headerSize: number
): { top: number; left: number } {
  const [r, c] = key.split(",").map(Number);
  const top  = GRID_PAD + headerSize + gap + r * (wellSize + gap);
  const left = GRID_PAD + headerSize + gap + c * (wellSize + gap);
  return { top, left };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function shuffleArr<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * 18–22 s progress ramp + shuffle burst every ~700 ms.
 * Only assigned wells become tokens; the shuffle pool is the full
 * set of usable positions so tokens can travel to empty wells.
 * onComplete fires once when the animation reaches 100%.
 */
export function useWaitingTroll(
  active: boolean,
  initialAssignments: WellAssignment[],
  allUsableKeys: string[],
  onComplete?: () => void
) {
  const [tokens, setTokens] = useState<TrollToken[]>([]);
  const [progress, setProgress] = useState(0);

  const rafRef          = useRef<number | null>(null);
  const timerRef        = useRef<ReturnType<typeof setInterval> | null>(null);
  const onCompleteRef   = useRef(onComplete);
  const usableKeysRef   = useRef(allUsableKeys);
  const activeRef       = useRef(active);
  onCompleteRef.current = onComplete;
  usableKeysRef.current = allUsableKeys;
  activeRef.current     = active;

  useEffect(() => {
    if (!active) {
      if (rafRef.current)   cancelAnimationFrame(rafRef.current);
      if (timerRef.current) clearInterval(timerRef.current);
      setTokens([]);
      setProgress(0);
      return;
    }

    let current: TrollToken[] = initialAssignments.map((a, i) => ({
      id: i,
      key: a.key,
      color: a.color,
    }));
    setTokens([...current]);

    // 15 s progress ramp — loops automatically if the solver hasn't finished yet.
    const dur = 15_000;
    let cycleStart = performance.now();
    function tick(now: number) {
      const pct = Math.min(100, ((now - cycleStart) / dur) * 100);
      setProgress(pct);
      if (pct < 100) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        // Notify the caller that one cycle finished.
        onCompleteRef.current?.();
        // If the caller kept us active (solver not done yet), loop for another cycle.
        if (activeRef.current) {
          cycleStart = performance.now();
          rafRef.current = requestAnimationFrame(tick);
        } else {
          // Caller deactivated us — stop the shuffle interval too.
          if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
        }
      }
    }
    rafRef.current = requestAnimationFrame(tick);

    // Shuffle burst: redistribute ALL tokens to n distinct random positions
    // drawn from the full usable pool (so tokens can land on empty wells).
    timerRef.current = setInterval(() => {
      const n = current.length;
      if (n < 2) return;
      const newKeys = shuffleArr([...usableKeysRef.current]).slice(0, n);
      current = current.map((t, i) => ({ ...t, key: newKeys[i] }));
      setTokens([...current]);
    }, 700);

    return () => {
      if (rafRef.current)   cancelAnimationFrame(rafRef.current);
      if (timerRef.current) clearInterval(timerRef.current);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  return { tokens, progress };
}

// ---------------------------------------------------------------------------
// TrollOverlay — absolutely positioned tokens inside .design-plate-grid-wrapper
// ---------------------------------------------------------------------------

interface TrollOverlayProps {
  tokens: TrollToken[];
  wellSize: number;
  gap: number;
  headerSize: number;
}

export function TrollOverlay({ tokens, wellSize, gap, headerSize }: TrollOverlayProps) {
  // Track which token ids are currently "in flight" (mid-move)
  const [moving, setMoving] = useState<Set<number>>(new Set());
  const prevKeysRef = useRef<Map<number, string>>(new Map());

  useEffect(() => {
    if (tokens.length === 0) return;
    const movers = new Set<number>();
    tokens.forEach((t) => {
      const prev = prevKeysRef.current.get(t.id);
      if (prev !== undefined && prev !== t.key) movers.add(t.id);
      prevKeysRef.current.set(t.id, t.key);
    });
    if (movers.size === 0) return;

    setMoving(movers);
    // After transition completes, unmark (land)
    const tid = setTimeout(() => setMoving(new Set()), 650);
    return () => clearTimeout(tid);
  }, [tokens]);

  return (
    <div className="wt-overlay">
      {tokens.map((t) => {
        const { top, left } = wellTopLeft(t.key, wellSize, gap, headerSize);
        const isMoving = moving.has(t.id);
        return (
          <div
            key={t.id}
            className={`wt-token${isMoving ? " wt-token-moving" : ""}`}
            style={{
              width:      wellSize,
              height:     wellSize,
              top,
              left,
              background: t.color,
            } as React.CSSProperties}
          />
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Progress bar component
// ---------------------------------------------------------------------------

export function TrollProgressBar({ progress }: { progress: number }) {
  return (
    <div className="wt-progress-wrap">
      <div className="wt-bar-track">
        <div className="wt-bar-fill" style={{ width: `${progress}%` }} />
      </div>
      <span className="wt-label">Solving layout…&nbsp;{Math.round(progress)}%</span>
    </div>
  );
}
