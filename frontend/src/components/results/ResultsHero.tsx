import { Link } from "react-router-dom";

import { apiClient } from "../../services/apiClient";
import type { JobRecord } from "../../types";
import "./ResultsHero.css";

type ResultsHeroProps = {
  job: JobRecord;
};

export function ResultsHero({ job }: ResultsHeroProps) {
  return (
    <section className="panel-surface results-hero">
      <div className="results-hero-copy">
        <p className="section-kicker">iPLAID · Run results</p>
        <h2>{job.config.protocol_name}</h2>
        <div className="results-hero-meta">
          <span className={`status-pill is-${job.status}`}>{job.status}</span>
          {job.finishedAt ? (
            <span className="results-hero-timestamp">
              Finished {new Date(job.finishedAt).toLocaleString()}
            </span>
          ) : null}
        </div>
      </div>
      <div className="results-hero-actions">
        {job.artifacts.map((artifact) => (
          <a
            key={artifact.name}
            className="primary-action compact"
            href={apiClient.artifactUrl(job.jobId, artifact.name)}
            download
          >
            {artifact.label}
          </a>
        ))}
        <Link className="secondary-action" to="/">
          New run
        </Link>
      </div>
    </section>
  );
}
