export type RunStatus = "queued" | "running" | "completed" | "failed";
export type DesignPhase = "queued" | "preflight" | "solving" | "completed" | "failed";

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

export type SolventDef = {
  name: string;
  replicates: number;
};

export type DesignConfig = {
  plate_rows: number;
  plate_cols: number;
  empty_edge: number;
  compounds: CompoundDef[];
  solvents: SolventDef[];
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
  warnings?: string[];
  summary?: {
    compoundCount: number;
    concentrationEntryCount: number;
    solventCount: number;
    totalSamples: number;
    usableWellsPerPlate: number;
    estimatedMinimumPlates: number;
  };
};

export type DesignPreflightReport = {
  ok: boolean;
  errors: string[];
  warnings: string[];
  summary: {
    compoundCount: number;
    concentrationEntryCount: number;
    solventCount: number;
    totalSamples: number;
    usableWellsPerPlate: number;
    estimatedMinimumPlates: number;
  };
};

export type DesignJob = {
  jobId: string;
  jobType: "design";
  status: RunStatus;
  phase: DesignPhase;
  createdAt: string;
  updatedAt: string;
  startedAt?: string;
  finishedAt?: string;
  designConfig: DesignConfig;
  preflight: DesignPreflightReport | null;
  layoutPreview: LayoutPreview | null;
  artifacts: ArtifactInfo[];
  numPlates?: number;
  numWells?: number;
  error: { message: string; details: string } | null;
};

// ---------------------------------------------------------------------------
// Existing pipeline types (unchanged)
// ---------------------------------------------------------------------------

export type DispenserName = "idot" | "echo";

export type RunConfig = {
  user_name: string;
  protocol_name: string;
  layout_file: string;
  meta_file: string;
  dispenser: DispenserName;
  source_layout_file?: string | null;
  sourceplate_type: string;
  target_plate_type: string;
  working_volume_ul: number;
  max_dmso_pct: number;
  solvent_caps_pct?: Record<string, number> | null;
  source_prep_overage_pct: number;
  min_pipette_volume_uL: number;
  dilution_solvent: string;
  source_well_fill_pct: number;
  standard_prep_volume_uL: number;
  output_timestamp_format: string;
};

export type SolventSummary = {
  solvent: string;
  solventKey: string;
  configuredCapPct: number;
  maxSolventUl: number;
  targetSolventUl: number;
  compoundWellCount: number;
  controlWellCount: number;
  topupDispenseCount: number;
};

export type PreflightSolventFamily = {
  solvent: string;
  solventKey: string;
  compoundCount: number;
  compoundWellCount: number;
  controlWellCount: number;
  configuredCapPct: number;
  requiredCapPct: number;
  status: "ok" | "warning" | "error";
};

export type PreflightRequirement = {
  compound: string;
  targetConcUm: number;
  highestStockMm: number;
  solvent: string;
  configuredCapPct: number;
  requiredSolventPct: number | null;
  feasible: boolean;
  reason: string;
  wellCount: number;
  status: "ok" | "needs_config" | "error";
};

export type PreflightAssessment = {
  ok: boolean;
  summary: {
    compoundRowsChecked: number;
    uniqueCompoundTargets: number;
    solventFamilyCount: number;
    warningCount: number;
    blockingIssueCount: number;
  };
  warnings: string[];
  blockingIssues: string[];
  solventFamilies: PreflightSolventFamily[];
  requirements: PreflightRequirement[];
  capRecommendations: Array<{
    solvent: string;
    configuredCapPct: number;
    requiredCapPct: number;
  }>;
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
  solventFamilyCount: number;
  solventSummary: SolventSummary[];
  targetDmsoUl: number;
  maxDmsoUl: number;
};

export type JobError = {
  message: string;
  details: string;
  preflight?: PreflightAssessment | null;
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
  preflight: PreflightAssessment | null;
  artifacts: ArtifactInfo[];
  liquidsPreview: Array<Record<string, string | number | boolean>>;
  stockSummary: Array<Record<string, string | number | boolean>>;
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

export type DispenserMeta = {
  name: DispenserName;
  display_name: string;
  default_sourceplate_type: string;
  default_target_plate_type: string;
  min_increment_nL: number;
};

export type BootstrapResponse = {
  configTemplate: RunConfig;
  sourcePlateTypes: string[];
  sourcePlateDefinitions: TargetPlateDefinition[];
  targetPlateTypes: string[];
  targetPlateDefinitions: TargetPlateDefinition[];
  solverCpus: number;
  dispensers: DispenserMeta[];
  plate_types_by_dispenser: Record<string, string[]>;
};
