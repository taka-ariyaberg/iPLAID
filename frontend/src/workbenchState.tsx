import {
  createContext,
  useContext,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from "react";

import type { CompoundRow as MetaCompoundRow } from "./components/workbench/MetaCreatorModal";
import type {
  BootstrapResponse,
  DesignConfig,
  DesignJob,
  LayoutPreview,
  RunConfig,
  SolventFamily,
} from "./types";

type WorkbenchState = {
  bootstrap: BootstrapResponse | null;
  config: RunConfig | null;
  loadingBootstrap: boolean;
  errorMessage: string | null;
  layoutFile: File | null;
  metaFile: File | null;
  preview: LayoutPreview | null;
  processing: boolean;
  isEditMode: boolean;
  workingPreview: LayoutPreview | null;
  showConfirmRun: boolean;
  revertKey: number;
  showClearLayoutWarning: boolean;
  layoutInputKey: number;
  metaInputKey: number;
  viewerPlateTypeId: string;
  customRows: number;
  customCols: number;
  layoutSource: "upload" | "design" | null;
  metaSource: "upload" | "created" | null;
  designActive: boolean;
  designConfig: DesignConfig | null;
  designJob: DesignJob | null;
  designIsGenerating: boolean;
  metaCreatorOpen: boolean;
  metaCreatorRows: MetaCompoundRow[];
  // Per-solvent cap view-state. Persisted alongside config so the Solvent
  // dropdown survives a navigation round-trip (run -> results -> back to
  // workbench). Still never written into config_json — only the
  // solvent_caps_pct map travels in config.
  solventFamilies: SolventFamily[];
  selectedSolventKey: string;
};

const initialWorkbenchState: WorkbenchState = {
  bootstrap: null,
  config: null,
  loadingBootstrap: true,
  errorMessage: null,
  layoutFile: null,
  metaFile: null,
  preview: null,
  processing: false,
  isEditMode: false,
  workingPreview: null,
  showConfirmRun: false,
  revertKey: 0,
  showClearLayoutWarning: false,
  layoutInputKey: 0,
  metaInputKey: 0,
  viewerPlateTypeId: "MWP 384",
  customRows: 16,
  customCols: 24,
  layoutSource: null,
  metaSource: null,
  designActive: false,
  designConfig: null,
  designJob: null,
  designIsGenerating: false,
  metaCreatorOpen: false,
  metaCreatorRows: [],
  solventFamilies: [],
  selectedSolventKey: "",
};

type WorkbenchStateContextValue = {
  state: WorkbenchState;
  setState: Dispatch<SetStateAction<WorkbenchState>>;
};

const WorkbenchStateContext = createContext<WorkbenchStateContextValue | null>(null);

export function WorkbenchStateProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<WorkbenchState>(initialWorkbenchState);

  return (
    <WorkbenchStateContext.Provider value={{ state, setState }}>
      {children}
    </WorkbenchStateContext.Provider>
  );
}

export function useWorkbenchField<K extends keyof WorkbenchState>(
  field: K,
): [WorkbenchState[K], Dispatch<SetStateAction<WorkbenchState[K]>>] {
  const context = useWorkbenchStateContext();

  const setField: Dispatch<SetStateAction<WorkbenchState[K]>> = (value) => {
    context.setState((current) => ({
      ...current,
      [field]:
        typeof value === "function"
          ? (value as (previous: WorkbenchState[K]) => WorkbenchState[K])(current[field])
          : value,
    }));
  };

  return [context.state[field], setField];
}

function useWorkbenchStateContext(): WorkbenchStateContextValue {
  const context = useContext(WorkbenchStateContext);
  if (!context) {
    throw new Error("Workbench state is only available inside WorkbenchStateProvider.");
  }
  return context;
}
