import "./WorkbenchHero.css";

type WorkbenchHeroProps = {
  isReady: boolean;
};

export function WorkbenchHero({ isReady }: WorkbenchHeroProps) {
  return (
    <section className="workbench-hero panel-surface">
      <div className="workbench-hero-copy">
        <p className="section-kicker">iPLAID</p>
        <h2>Prepare your plate map and generate run files</h2>
        <p>
          Upload a layout and metadata CSV, review the well assignments across the target plate,
          then configure and submit your iPLAID run.
        </p>
      </div>
      <aside className="hero-status-card">
        <span className="hero-status-label">Status</span>
        <strong className={`hero-status-value is-${isReady ? "ready" : "missing-files"}`}>
          {isReady ? "Ready to run" : "Awaiting files"}
        </strong>
      </aside>
    </section>
  );
}
