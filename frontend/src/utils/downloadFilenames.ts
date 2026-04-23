const DOWNLOAD_PREFIX = "iPLAID";

const INVALID_SEGMENT_RE = /[^A-Za-z0-9]+/g;
const DUPLICATE_UNDERSCORE_RE = /_+/g;

function sanitizeFilenameSegment(value: string | null | undefined, fallback = "unnamed"): string {
  const raw = (value ?? "").trim();
  if (!raw) return fallback;

  const sanitized = raw
    .replace(INVALID_SEGMENT_RE, "_")
    .replace(DUPLICATE_UNDERSCORE_RE, "_")
    .replace(/^_+|_+$/g, "");

  return sanitized || fallback;
}

export function buildDownloadProjectDetails(...parts: Array<string | null | undefined>): string {
  const cleaned = parts
    .map((part) => sanitizeFilenameSegment(part, ""))
    .filter(Boolean);
  return cleaned.length > 0 ? cleaned.join("_") : "session";
}

export function formatDownloadTimestamp(date = new Date()): string {
  const yy = String(date.getFullYear() % 100).padStart(2, "0");
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const dd = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const min = String(date.getMinutes()).padStart(2, "0");
  const ss = String(date.getSeconds()).padStart(2, "0");
  return `${yy}-${mm}-${dd}-${hh}-${min}-${ss}`;
}

export function buildDownloadFilename({
  projectDetails,
  artifact,
  extension,
  timestamp = new Date(),
}: {
  projectDetails: string | string[];
  artifact: string;
  extension: string;
  timestamp?: Date;
}): string {
  const projectPart = Array.isArray(projectDetails)
    ? buildDownloadProjectDetails(...projectDetails)
    : buildDownloadProjectDetails(projectDetails);
  const artifactPart = sanitizeFilenameSegment(artifact, "artifact");
  const ext = extension.startsWith(".") ? extension : `.${extension}`;

  return `${DOWNLOAD_PREFIX}_${projectPart}_${artifactPart}_${formatDownloadTimestamp(timestamp)}${ext}`;
}

export function buildPlateExportFilename(
  projectDetails: string | string[],
  scope: "target" | "source" | "workbench",
  extension: "csv" | "png" | "svg",
): string {
  const artifact = extension === "csv" ? `${scope}_plate_layout` : `${scope}_plate_figure`;
  return buildDownloadFilename({
    projectDetails,
    artifact,
    extension,
  });
}

export function buildDesignExportFilename(
  projectDetails: string | string[],
  extension: "csv" | "png" | "svg",
): string {
  const artifact = extension === "csv" ? "designed_layout" : "designed_layout_figure";
  return buildDownloadFilename({
    projectDetails,
    artifact,
    extension,
  });
}

export function buildMetaExportFilename(projectDetails: string | string[]): string {
  return buildDownloadFilename({
    projectDetails,
    artifact: "compound_metadata",
    extension: "csv",
  });
}
