import React, { useEffect, useMemo, useRef, useState } from "react";

import type { DesignPhase } from "../../types";
import "./WaitingTroll.css";

export interface WellAssignment {
  key: string;
  color: string;
}

export interface TrollToken {
  id: number;
  key: string;
  color: string;
}

function shuffleArr<T>(arr: T[]): T[] {
  const next = [...arr];
  for (let index = next.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    [next[index], next[swapIndex]] = [next[swapIndex], next[index]];
  }
  return next;
}

const GRID_PAD = 20;

function wellTopLeft(
  key: string,
  wellSize: number,
  gap: number,
  headerSize: number,
): { top: number; left: number } {
  const [row, col] = key.split(",").map(Number);
  return {
    top: GRID_PAD + headerSize + gap + row * (wellSize + gap),
    left: GRID_PAD + headerSize + gap + col * (wellSize + gap),
  };
}

export function useWaitingTroll(
  active: boolean,
  initialAssignments: WellAssignment[],
  allUsableKeys: string[],
) {
  const [tokens, setTokens] = useState<TrollToken[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!active) {
      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = null;
      setTokens([]);
      return;
    }

    let current = initialAssignments.map((assignment, index) => ({
      id: index,
      key: assignment.key,
      color: assignment.color,
    }));
    setTokens(current);

    timerRef.current = setInterval(() => {
      const count = current.length;
      if (count < 2) return;
      const nextKeys = shuffleArr(allUsableKeys).slice(0, count);
      current = current.map((token, index) => ({ ...token, key: nextKeys[index] }));
      setTokens([...current]);
    }, 900);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = null;
    };
  }, [active, initialAssignments, allUsableKeys]);

  return { tokens };
}

export function TrollOverlay({
  tokens,
  wellSize,
  gap,
  headerSize,
}: {
  tokens: TrollToken[];
  wellSize: number;
  gap: number;
  headerSize: number;
}) {
  const [moving, setMoving] = useState<Set<number>>(new Set());
  const previousKeysRef = useRef<Map<number, string>>(new Map());

  useEffect(() => {
    if (tokens.length === 0) return;

    const movers = new Set<number>();
    tokens.forEach((token) => {
      const previous = previousKeysRef.current.get(token.id);
      if (previous !== undefined && previous !== token.key) {
        movers.add(token.id);
      }
      previousKeysRef.current.set(token.id, token.key);
    });

    if (movers.size === 0) return;
    setMoving(movers);
    const timeoutId = window.setTimeout(() => setMoving(new Set()), 650);
    return () => window.clearTimeout(timeoutId);
  }, [tokens]);

  return (
    <div className="wt-overlay">
      {tokens.map((token) => {
        const { top, left } = wellTopLeft(token.key, wellSize, gap, headerSize);
        return (
          <div
            key={token.id}
            className={`wt-token${moving.has(token.id) ? " wt-token-moving" : ""}`}
            style={{
              width: wellSize,
              height: wellSize,
              top,
              left,
              background: token.color,
            }}
          />
        );
      })}
    </div>
  );
}

function phaseLabel(phase: DesignPhase): string {
  switch (phase) {
    case "preflight":
      return "Running design preflight…";
    case "solving":
      return "Generating layout with PLAID_Core…";
    case "completed":
      return "Layout ready.";
    case "failed":
      return "Design failed.";
    default:
      return "Preparing design…";
  }
}

function phaseClass(phase: DesignPhase): string {
  switch (phase) {
    case "solving":
      return "is-solving";
    case "completed":
      return "is-complete";
    case "failed":
      return "is-failed";
    default:
      return "is-preflight";
  }
}

export function TrollStatusBar({ phase }: { phase: DesignPhase }) {
  const label = useMemo(() => phaseLabel(phase), [phase]);
  return (
    <div className="wt-progress-wrap">
      <div className="wt-bar-track">
        <div className={`wt-bar-fill ${phaseClass(phase)}`} />
      </div>
      <span className="wt-label">{label}</span>
    </div>
  );
}
