import { useEffect, useRef, useState } from "react";

export type ConfigDropdownOption = { value: string; label: string };

type ConfigDropdownProps = {
  value: string;
  options: ConfigDropdownOption[];
  onChange: (value: string) => void;
  ariaLabel?: string;
};

/**
 * Custom dropdown used for the Configuration panel's Dispenser and Source
 * plate type fields. Replaces a native <select> so the opened menu is a
 * styled list (matches the rest of the dark UI) rather than the OS popover
 * that Safari/Chrome render on macOS.
 */
export function ConfigDropdown({ value, options, onChange, ariaLabel }: ConfigDropdownProps) {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDocMouseDown(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocMouseDown);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDocMouseDown);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  const selected = options.find((o) => o.value === value);

  return (
    <div className={`config-dropdown${open ? " is-open" : ""}`} ref={wrapperRef}>
      <button
        type="button"
        className="config-dropdown-trigger"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="config-dropdown-trigger-label">
          {selected?.label ?? value}
        </span>
        <svg
          className="config-dropdown-chevron"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {open && (
        <div className="config-dropdown-menu" role="listbox">
          {options.map((opt) => (
            <button
              key={opt.value}
              type="button"
              role="option"
              aria-selected={opt.value === value}
              className={`config-dropdown-item${opt.value === value ? " is-selected" : ""}`}
              onClick={() => {
                onChange(opt.value);
                setOpen(false);
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
