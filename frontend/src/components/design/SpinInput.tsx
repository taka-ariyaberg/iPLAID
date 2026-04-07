/**
 * SpinInput — split number input used throughout Design mode.
 *
 * Left side: plain text field (value centred, freely editable).
 * Right side: ▲ / ▼ buttons in a narrow column.
 *
 * No browser-native spinner chrome is shown.
 */

import { useEffect, useRef, useState } from "react";

export interface SpinInputProps {
  value: number;
  min?: number;
  max?: number;
  step?: number;
  placeholder?: string;
  /** Extra class(es) applied to the wrapper div alongside "spin-input" */
  className?: string;
  onChange: (v: number) => void;
  /** Called on blur after the value is clamped — use to enforce minimums etc. */
  onCommit?: (v: number) => void;
  readOnly?: boolean;
}

export function SpinInput({
  value,
  min = -Infinity,
  max = Infinity,
  step = 1,
  placeholder,
  className = "",
  onChange,
  onCommit,
  readOnly = false,
}: SpinInputProps) {
  const [draft, setDraft] = useState(value === 0 && placeholder ? "" : String(value));
  const prevValueRef = useRef(value);

  // Sync when upstream changes the value externally
  useEffect(() => {
    if (value !== prevValueRef.current) {
      setDraft(value === 0 && placeholder ? "" : String(value));
      prevValueRef.current = value;
    }
  }, [value, placeholder]);

  const clamp = (n: number) =>
    Math.min(max === Infinity ? n : max, Math.max(min === -Infinity ? n : min, n));

  const commit = (raw: string) => {
    const fallback = min === -Infinity ? 0 : min;
    const parsed = raw === "" ? fallback : Number(raw);
    const clamped = clamp(isNaN(parsed) ? fallback : parsed);
    prevValueRef.current = clamped;
    setDraft(clamped === 0 && placeholder ? "" : String(clamped));
    onCommit?.(clamped);
  };

  const nudge = (delta: number) => {
    const current = draft === "" ? (min === -Infinity ? 0 : min) : Number(draft) || 0;
    const next = clamp(current + delta);
    prevValueRef.current = next;
    setDraft(next === 0 && placeholder ? "" : String(next));
    onChange(next);
  };

  if (readOnly) {
    return <span className="design-num-readonly">{value}</span>;
  }

  return (
    <div className={`spin-input ${className}`.trim()}>
      <input
        type="text"
        inputMode="decimal"
        placeholder={placeholder}
        className="spin-input-field"
        value={draft}
        onChange={(e) => {
          const raw = e.target.value;
          setDraft(raw);
          const parsed = raw === "" ? 0 : Number(raw);
          if (!isNaN(parsed)) {
            const clamped = clamp(parsed);
            prevValueRef.current = clamped;
            onChange(clamped);
          }
        }}
        onBlur={(e) => commit(e.target.value)}
        onFocus={(e) => e.target.select()}
        onKeyDown={(e) => {
          if (e.key === "ArrowUp")   { e.preventDefault(); nudge(+step); }
          if (e.key === "ArrowDown") { e.preventDefault(); nudge(-step); }
          if (e.key === "Enter")     { e.preventDefault(); commit((e.target as HTMLInputElement).value); }
        }}
      />
      <div className="spin-input-arrows">
        <button
          type="button"
          className="spin-arrow spin-arrow-up"
          tabIndex={-1}
          onMouseDown={(e) => { e.preventDefault(); nudge(+step); }}
          aria-label="Increase"
        >▲</button>
        <button
          type="button"
          className="spin-arrow spin-arrow-down"
          tabIndex={-1}
          onMouseDown={(e) => { e.preventDefault(); nudge(-step); }}
          aria-label="Decrease"
        >▼</button>
      </div>
    </div>
  );
}
