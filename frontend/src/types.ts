export type RunStatus = "queued" | "running" | "completed" | "failed";

// ---------------------------------------------------------------------------
// Design (PLAID_Core) types
// ---------------------------------------------------------------------------

/** One concentration entry: a µM value plus how many replicates to place */
export type ConcEntry = {
  value_um: number;
  replicates: number;
};

export type CompoundDef = {
  name: string;
  conc_entries: ConcEntry[];
};

export type ControlDef = {
  name: string;
  conc_entries: ConcEntry[];
};

export type DesignConfig = {
  plate_rows: number;
  plate_cols: number;
  empty_edge: number;
  compounds: CompoundDef[];
  controls: ControlDef[];
  concentrations_on_different_rows: boolean;
  concentrations_on_different_columns: boolean;
  replicates_on_same_plate: boolean;
  replicates_on_different_plates: boolean;
  allow_empty_wells: boolean;
  balance_controls_inside_plate: boolean;
  interconnected_plates: boolean;
  control_slack: number;
  force_spread_controls: boolean;
  force_spread_concentrations: boolean;
  horizontal_cell_lines: number;
  vertical_cell_lines: number;
  timeout_seconds: number;
  num_threads: number;
  random_seed: number | null;
};

export type ValidationResult = {
  ok: boolean;
  errors: string[];
};

export type DesignJob = {
  jobId: string;
  jobType: "design";
  status: RunStatus;
  createdAt: string;
  updatedAt: string;
  startedAt?: string;
  finishedAt?: string;
  designConfig: DesignConfig;
  layoutPreview: LayoutPreview | null;
  artifacts: ArtifactInfo[];
  numPlates?: number;
  numWells?: number;
  error: { message: string; details: string } | null;
};

// ---------------------------------------------------------------------------
// Existing pipeline types (unchanged)
// ---------------------------------------------------------------------------

export type RunConfig = {
  user_name: string;
  protocol_name: string;
  layout_file: string;
  meta_file: string;
  sourceplate_type: string;
  target_plate_type: string;
  working_volume_ul: number;
  max_dmso_pct: number;
  source_prep_overage_pct: number;
  min_pipette_volume_uL: number;
  dilution_solvent: string;
  source_well_fill_pct: number;
  standard_prep_volume_uL: number;
  output_timestamp_format: string;
};

export type CompoundSummary = {
  name: string;
  count: number;
};

export type PlateWell = {
  well: string;
  rowLabel: string;
  column: number;
  compound: string;
  concentration: number | null;
  isControl: boolean;
};

export type PlatePreview = {
  plateId: string;
  rowLabels: string[];
  columnLabels: number[];
  wells: PlateWell[];
};

export type LayoutPreview = {
  plates: PlatePreview[];
  compoundSummary: CompoundSummary[];
  plateCount: number;
  wellCount: number;
  concentrationSummary: {
    min: number | null;
    max: number | null;
  };
};

export type ArtifactInfo = {
  name: string;
  label: string;
};

export type RunSummary = {
  inputRows: number;
  dispenseRows: number;
  uniqueLiquids: number;
  plateCount: number;
  targetDmsoUl: number;
  maxDmsoUl: number;
};

export type JobError = {
  message: string;
  details: string;
};

export type JobRecord = {
  jobId: string;
  status: RunStatus;
  createdAt: string;
  updatedAt: string;
  startedAt?: string;
  finishedAt?: string;
  config: RunConfig;
  preview: LayoutPreview;
  resultPreview: LayoutPreview | null;
  summary: RunSummary | null;
  artifacts: ArtifactInfo[];
  liquidsPreview: Array<Record<string, string | number>>;
  stockSummary: Array<Record<string, string | number>>;
  sourceWellTargetMap?: Record<string, string[]>;
  error: JobError | null;
};

export type TargetPlateDefinition = {
  id: string;
  label: string;
  rows: number;
  cols: number;
  wells: number;
};

export type BootstrapResponse = {
  configTemplate: RunConfig;
  sourcePlateTypes: string[];
  sourcePlateDefinitions: TargetPlateDefinition[];
  targetPlateTypes: string[];
  targetPlateDefinitions: TargetPlateDefinition[];
};