import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { PlateGrid } from "../components/PlateGrid";
import { ResultsHero } from "../components/results/ResultsHero";
import { SourcePlatePanel } from "../components/results/SourcePlatePanel";
import { apiClient } from "../services/apiClient";
import type { BootstrapResponse, JobRecord } from "../types";
import "../styles/ResultsPage.css";

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
  const targetPlateDef = bootstrap?.targetPlateDefinitions.find(
    (d) => d.id === job.config.target_plate_type,
  );
  const sourcePlateDef = bootstrap?.sourcePlateDefinitions.find(
    (d) => d.id === job.config.sourceplate_type,
  );

  return (
    <div className="results-layout">
      <ResultsHero job={job} />

      {errorMessage && (
        <section className="status-banner is-error">{errorMessage}</section>
      )}
      {job.error && (
        <section className="panel-surface results-error-block">
          <p className="section-kicker">Pipeline failure</p>
          <h3>{job.error.message}</h3>
          <pre>{job.error.details}</pre>
        </section>
      )}

      <PlateGrid
        preview={targetPreview}
        title={job.status === "completed" ? "Processed target plate layout" : "Submitted target plate layout"}
        plateDef={targetPlateDef}
        showDefaultTooltip
      />

      <SourcePlatePanel job={job} plateDef={sourcePlateDef} />
    </div>
  );
}
