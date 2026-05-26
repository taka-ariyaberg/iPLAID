import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { PlateGrid } from "../components/PlateGrid";
import { ResultsHero } from "../components/results/ResultsHero";
import { SourcePlatePanel } from "../components/results/SourcePlatePanel";
import { apiClient } from "../services/apiClient";
import type { BootstrapResponse, JobRecord, PreflightAssessment } from "../types";
import { canonicalWellId } from "../utils/wellUtils";
import "../styles/ResultsPage.css";

function formatPct(value: number): string {
  return `${value.toFixed(3)}%`;
}

function PreflightPanel({ assessment, failed }: { assessment: PreflightAssessment; failed: boolean }) {
  const flaggedRequirements = assessment.requirements.filter((item) => item.status !== "ok");

  return (
    <section className="panel-surface results-preflight-block">
      <div className="results-preflight-header">
        <div>
          <p className="section-kicker">Run assessment</p>
          <h3>Pre-flight {failed ? "blocked the run" : "warnings"}</h3>
        </div>
        <span className={`status-pill ${failed ? "is-failed" : "is-running"}`}>
          {failed ? "blocked" : "warning"}
        </span>
      </div>

      <p className="results-preflight-summary">
        Checked {assessment.summary.uniqueCompoundTargets} unique compound targets across{" "}
        {assessment.summary.solventFamilyCount} solvent{" "}
        {assessment.summary.solventFamilyCount === 1 ? "family" : "families"}.
      </p>

      {assessment.warnings.length > 0 && (
        <div className="results-preflight-section">
          <h4>Warnings</h4>
          <ul className="results-preflight-list">
            {assessment.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {assessment.blockingIssues.length > 0 && (
        <div className="results-preflight-section">
          <h4>Blocking issues</h4>
          <ul className="results-preflight-list">
            {assessment.blockingIssues.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        </div>
      )}

      {assessment.capRecommendations.length > 0 && (
        <div className="results-preflight-section">
          <h4>Cap adjustments</h4>
          <ul className="results-preflight-list">
            {assessment.capRecommendations.map((item) => (
              <li key={item.solvent}>
                {item.solvent}: {formatPct(item.configuredCapPct)} → at least {formatPct(item.requiredCapPct)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {assessment.solventFamilies.length > 0 && (
        <div className="results-preflight-section">
          <h4>Solvent families</h4>
          <div className="results-preflight-grid">
            {assessment.solventFamilies.map((family) => (
              <article key={family.solventKey} className={`results-preflight-card is-${family.status}`}>
                <div className="results-preflight-card-head">
                  <strong>{family.solvent}</strong>
                  <span>{family.controlWellCount} solvent-only well{family.controlWellCount === 1 ? "" : "s"}</span>
                </div>
                <p>{family.compoundCount} compound{family.compoundCount === 1 ? "" : "s"} • {family.compoundWellCount} wells</p>
                <p>Configured cap: {formatPct(family.configuredCapPct)}</p>
                <p>Required cap: {formatPct(family.requiredCapPct)}</p>
              </article>
            ))}
          </div>
        </div>
      )}

      {flaggedRequirements.length > 0 && (
        <div className="results-preflight-section">
          <h4>Affected targets</h4>
          <div className="results-preflight-table-wrap">
            <table className="results-preflight-table">
              <thead>
                <tr>
                  <th>Compound</th>
                  <th>Target</th>
                  <th>Solvent</th>
                  <th>Configured</th>
                  <th>Required</th>
                </tr>
              </thead>
              <tbody>
                {flaggedRequirements.map((item) => (
                  <tr key={`${item.compound}-${item.targetConcUm}-${item.solvent}`}>
                    <td>{item.compound}</td>
                    <td>{item.targetConcUm} uM</td>
                    <td>{item.solvent}</td>
                    <td>{formatPct(item.configuredCapPct)}</td>
                    <td>{item.requiredSolventPct == null ? item.reason : formatPct(item.requiredSolventPct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

export function ResultsPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [job, setJob] = useState<JobRecord | null>(null);
  const [bootstrap, setBootstrap] = useState<BootstrapResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    void apiClient.getBootstrap().then(setBootstrap).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!jobId) return;

    const resolvedJobId = jobId;
    let cancelled = false;
    let timerId: number | undefined;

    async function loadRun() {
      try {
        const payload = await apiClient.getRun(resolvedJobId);
        if (cancelled) return;
        setJob(payload);
        setErrorMessage(null);
        if (payload.status === "queued" || payload.status === "running") {
          timerId = window.setTimeout(() => { void loadRun(); }, 2000);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : "Failed to load run details.");
        }
      }
    }

    void loadRun();

    return () => {
      cancelled = true;
      if (timerId) window.clearTimeout(timerId);
    };
  }, [jobId]);

  if (!jobId) return <section className="page-state">Missing run identifier.</section>;
  if (!job) return <section className="page-state">Loading run...</section>;

  const targetPreview = job.resultPreview ?? job.preview;
  const preflightAssessment = job.error?.preflight ?? job.preflight;
  const hasPreflightNotes = Boolean(
    preflightAssessment &&
    (
      preflightAssessment.warnings.length > 0 ||
      preflightAssessment.blockingIssues.length > 0 ||
      preflightAssessment.capRecommendations.length > 0
    )
  );
  const targetPlateDefinitions =
    bootstrap?.target_plate_definitions_by_dispenser?.[job.config.dispenser] ??
    bootstrap?.targetPlateDefinitions;
  const targetPlateDef = targetPlateDefinitions?.find(
    (d) => d.id === job.config.target_plate_type,
  );
  const sourcePlateDefinitions =
    bootstrap?.source_plate_definitions_by_dispenser?.[job.config.dispenser] ??
    bootstrap?.sourcePlateDefinitions;
  const sourcePlateDef = sourcePlateDefinitions?.find(
    (d) => d.id === job.config.sourceplate_type,
  );

  // Wells that were skipped because their compound was excluded from the run.
  // PlateGrid keys cells as `${plateId}:${formatWellId(rowLabel, column)}` which
  // is the zero-padded canonical form (e.g. "plate_1:A01", "plate_1:D04",
  // "plate_1:D17"). The backend emits raw target_well strings that may be
  // unpadded (e.g. "D4", "A1"), so canonicalize before building the lookup set.
  const excludedWells = new Set(
    (job.excludedTargetWells ?? []).map(
      (etw) => `${etw.target_plate}:${canonicalWellId(etw.target_well)}`,
    ),
  );

  return (
    <div className="results-layout">
      <ResultsHero job={job} />

      {errorMessage && (
        <section className="status-banner is-error">{errorMessage}</section>
      )}
      {job.excludedCompounds && job.excludedCompounds.length > 0 && (
        <section className="status-banner is-error">
          ⚠️ The following compounds could not fit on the source plate and were excluded
          from the run. Their target wells will be empty (no dispense):
          <ul>
            {job.excludedCompounds.map((ec) => (
              <li key={ec.compound}>
                <strong>{ec.compound}</strong> — needed {ec.stocks_needed} stocks,
                {" "}{ec.free_wells_remaining} free wells remaining.
              </li>
            ))}
          </ul>
        </section>
      )}
      {job.warnings && job.warnings.some((w) => w.kind === "scatter") && (
        <section className="status-banner is-warning">
          ℹ️ Non-contiguous placements — the same-row rule was relaxed for these compounds
          due to space constraints:
          <ul>
            {job.warnings
              .filter((w) => w.kind === "scatter")
              .map((w) => (
                <li key={w.compound}>
                  <strong>{w.compound}</strong> placed at: {w.wells?.join(", ")}
                </li>
              ))}
          </ul>
        </section>
      )}
      {hasPreflightNotes && preflightAssessment && (
        <PreflightPanel
          assessment={preflightAssessment}
          failed={job.status === "failed" || !preflightAssessment.ok}
        />
      )}
      {job.error && (
        <section className="panel-surface results-error-block">
          <p className="section-kicker">Pipeline failure</p>
          <h3>{job.error.message}</h3>
          {!job.error.preflight && (
            <details className="results-error-details">
              <summary>Technical details</summary>
              <pre>{job.error.details}</pre>
            </details>
          )}
        </section>
      )}

      <PlateGrid
        preview={targetPreview}
        title={job.status === "completed" ? "Processed target plate layout" : "Submitted target plate layout"}
        plateDef={targetPlateDef}
        exportProjectDetails={[job.config.user_name, job.config.protocol_name]}
        exportScope="target"
        showDefaultTooltip
        excludedWells={excludedWells}
      />

      <SourcePlatePanel job={job} plateDef={sourcePlateDef} />
    </div>
  );
}
