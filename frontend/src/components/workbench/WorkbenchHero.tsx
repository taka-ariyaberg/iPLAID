import type { RunConfig } from "../../types";
import "./WorkbenchHero.css";

export type WorkbenchHeroRunningPhase =
  | { kind: "design"; label?: string }
  | { kind: "pipeline"; label?: string }
  | null;

type WorkbenchHeroProps = {
  layoutFile: File | null;
  metaFile: File | null;
  sourceLayoutFile: File | null;
  config: RunConfig | null;
  layoutWellCount: number | null;
  metaCompoundCount: number | null;
  running: WorkbenchHeroRunningPhase;
};

type StepStatus = "done" | "pending" | "optional";

type Step = {
  key: string;
  label: string;
  value: string;
  status: StepStatus;
};

function nextStepHint(steps: Step[]): string {
  const firstPending = steps.find((s) => s.status === "pending");
  if (firstPending) return `Next: ${firstPending.label.toLowerCase()}`;
  return "Ready to run";
}

export function WorkbenchHero({
  layoutFile,
  metaFile,
  sourceLayoutFile,
  config,
  layoutWellCount,
  metaCompoundCount,
  running,
}: WorkbenchHeroProps) {
  if (running) {
    return (
      <section className="workbench-hero panel-surface">
        <div className="workbench-hero-copy">
          <p className="section-kicker">iPLAID</p>
          <h2>Prepare your plate map and generate run files</h2>
          <p>
            Upload or design a layout and metadata CSV, review the well assignments across the target plate,
            then configure and submit your iPLAID run.
          </p>
        </div>
        <aside className="hero-status-card hero-status-running">
          <span className="hero-status-label">Status</span>
          <div className="hero-running-row">
            <span className="hero-running-spinner" />
            <strong className="hero-status-value is-running">
              {running.kind === "design" ? "Designing layout" : "Running iPLAID"}
            </strong>
          </div>
          {running.label && <span className="hero-running-phase">{running.label}</span>}
          {running.kind === "design" && (
            <p className="hero-running-hint">Click <em>Stop solver</em> in the design panel to cancel.</p>
          )}
        </aside>
      </section>
    );
  }

  const layoutFilename = layoutFile?.name;
  const metaFilename = metaFile?.name;
  const sourceLayoutFilename = sourceLayoutFile?.name;

  const layoutValue = layoutFilename
    ? layoutWellCount !== null
      ? `${layoutFilename} · ${layoutWellCount} wells`
      : layoutFilename
    : "drop a CSV to begin";

  const metaValue = sourceLayoutFilename
    ? `via ${sourceLayoutFilename}`
    : metaFilename
      ? metaCompoundCount !== null
        ? `${metaFilename} · ${metaCompoundCount} compounds`
        : metaFilename
      : "upload meta or source-plate layout";

  const dispenserLabel = config?.dispenser === "echo" ? "Echo" : "iDOT";
  const dispenserValue = config ? `${dispenserLabel} · ${config.sourceplate_type}` : "—";
  const targetValue = config ? config.target_plate_type : "—";

  const steps: Step[] = [
    {
      key: "layout",
      label: "Layout",
      value: layoutValue,
      status: layoutFilename ? "done" : "pending",
    },
    {
      key: "meta",
      label: "Metadata",
      value: metaValue,
      status: metaFilename || sourceLayoutFilename ? "done" : "pending",
    },
    {
      key: "dispenser",
      label: "Dispenser",
      value: dispenserValue,
      status: config ? "done" : "pending",
    },
    {
      key: "target",
      label: "Target plate",
      value: targetValue,
      status: config ? "done" : "pending",
    },
  ];

  const allDone = steps.every((s) => s.status === "done");
  const hint = allDone ? "Ready to run" : nextStepHint(steps);

  return (
    <section className="workbench-hero panel-surface">
      <div className="workbench-hero-copy">
        <p className="section-kicker">iPLAID</p>
        <h2>Prepare your plate map and generate run files</h2>
        <p>
          Upload or design a layout and metadata CSV, review the well assignments across the target plate,
          then configure and submit your iPLAID run.
        </p>
      </div>
      <aside className="hero-status-card">
        <span className="hero-status-label">Status</span>
        <ul className="hero-checklist">
          {steps.map((s) => (
            <li key={s.key} className={`hero-check-row is-${s.status}`}>
              <span className="hero-check-mark" aria-hidden>
                {s.status === "done" ? "✓" : "○"}
              </span>
              <span className="hero-check-label">{s.label}</span>
              <span className="hero-check-value" title={s.value}>{s.value}</span>
            </li>
          ))}
        </ul>
        <strong className={`hero-status-hint is-${allDone ? "ready" : "missing-files"}`}>
          {allDone ? "▶ " : ""}{hint}
        </strong>
      </aside>
    </section>
  );
}
