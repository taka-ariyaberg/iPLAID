import { useMemo } from "react";
import type { ReactNode } from "react";

import { PlateGrid } from "../PlateGrid";
import type {
  CompoundSummary,
  JobRecord,
  LayoutPreview,
  PlatePreview,
  PlateWell,
  TargetPlateDefinition,
} from "../../types";
import { parseLiquidName } from "../../utils/liquidUtils";

function buildSourcePlatePreview(
  liquidsPreview: Array<Record<string, string | number | boolean>>,
): LayoutPreview | null {
  if (!liquidsPreview.length) return null;

  const plateMap = new Map<string, PlateWell[]>();
  const compoundCounts = new Map<string, number>();

  for (const row of liquidsPreview) {
    const liquidName = String(row["Liquid Name"] ?? "");

    // New-format rows have `compound` and `stock_mM` pre-parsed by the backend.
    // Fall back to parsing `Liquid Name` for older stored job records.
    let compound: string;
    let stockMM: number | null;

    if ("compound" in row && "stock_mM" in row) {
      compound = String(row["compound"]);
      const raw = typeof row["stock_mM"] === "number" ? row["stock_mM"] : parseFloat(String(row["stock_mM"]));
      const isControlLiquid = Boolean(row["is_control_liquid"]) || (!isNaN(raw) && raw === 0);
      if (isControlLiquid) {
        stockMM = null;
      } else {
        stockMM = isNaN(raw) ? null : raw;
      }
    } else {
      ({ compound, stockMM } = parseLiquidName(liquidName));
    }

    const plateId = String(row["Source Plate"] ?? "");
    const wellStr = String(row["Source Well"] ?? "");

    const match = wellStr.match(/^([A-Za-z]+)(\d+)$/);
    if (!match) continue;

    const well: PlateWell = {
      well: wellStr,
      rowLabel: match[1].toUpperCase(),
      column: parseInt(match[2], 10),
      compound,
      concentration: stockMM,
      isControl: stockMM === null,
    };

    if (!plateMap.has(plateId)) plateMap.set(plateId, []);
    plateMap.get(plateId)!.push(well);
    compoundCounts.set(compound, (compoundCounts.get(compound) ?? 0) + 1);
  }

  const plates: PlatePreview[] = [];
  for (const [plateId, wells] of plateMap.entries()) {
    const rowSet = new Set(wells.map((w) => w.rowLabel));
    const maxCol = Math.max(...wells.map((w) => w.column));

    const firstCode = "A".charCodeAt(0);
    const lastCode = Math.max(...[...rowSet].map((r) => r.charCodeAt(0)));
    const rowLetters: string[] = [];
    for (let c = firstCode; c <= lastCode; c++) rowLetters.push(String.fromCharCode(c));

    const columnLabels = Array.from({ length: maxCol }, (_, i) => i + 1);
    plates.push({ plateId, rowLabels: rowLetters, columnLabels, wells });
  }

  const compoundSummary: CompoundSummary[] = [...compoundCounts.entries()].map(
    ([name, count]) => ({ name, count }),
  );

  return {
    plates,
    compoundSummary,
    plateCount: plates.length,
    wellCount: liquidsPreview.length,
    concentrationSummary: { min: null, max: null },
  };
}

type SourcePlatePanelProps = {
  job: JobRecord;
  plateDef: TargetPlateDefinition | undefined;
};

export function SourcePlatePanel({ job, plateDef }: SourcePlatePanelProps) {
  const sourcePlatePreview = useMemo(
    () => buildSourcePlatePreview(job.liquidsPreview),
    [job.liquidsPreview],
  );

  const wellTooltipContent = useMemo(() => {
    const wellInfoMap = new Map<string, { compound: string; stockMM: number | null; isControlLiquid: boolean }>();
    for (const row of job.liquidsPreview) {
      const sourceWell = String(row["Source Well"] ?? "");
      if (!sourceWell) continue;
      const compound = String(row["compound"] ?? "");
      const rawStock = row["stock_mM"];
      const parsed = typeof rawStock === "number" ? rawStock : parseFloat(String(rawStock));
      const isControlLiquid = Boolean(row["is_control_liquid"]) || (!isNaN(parsed) && parsed === 0);
      wellInfoMap.set(sourceWell, {
        compound,
        stockMM: isControlLiquid ? null : (isNaN(parsed) ? null : parsed),
        isControlLiquid,
      });
    }
    const targetMap = job.sourceWellTargetMap ?? {};

    return (wellId: string): ReactNode | null => {
      const colonIdx = wellId.indexOf(":");
      const wellName = wellId.slice(colonIdx + 1);
      const info = wellInfoMap.get(wellName);
      if (!info) return null;
      const { compound, stockMM, isControlLiquid } = info;
      const targetWells: string[] = targetMap[wellName] ?? [];
      const MAX_SHOWN = 30;
      return (
        <>
          <div className="well-tt-name">{wellName}</div>
          <div className="well-tt-compound">{compound}</div>
          {!isControlLiquid && stockMM != null && (
            <div className="well-tt-stock">{stockMM} mM stock</div>
          )}
          {isControlLiquid && <div className="well-tt-stock">Top-up solvent</div>}
          {targetWells.length > 0 && (
            <div className="well-tt-targets">
              <div className="well-tt-label">Target wells ({targetWells.length})</div>
              <div className="well-tt-wells">
                {targetWells.slice(0, MAX_SHOWN).join(", ")}
                {targetWells.length > MAX_SHOWN && <> +{targetWells.length - MAX_SHOWN} more</>}
              </div>
            </div>
          )}
        </>
      );
    };
  }, [job.liquidsPreview, job.sourceWellTargetMap]);

  const concBlockExtras = useMemo(() => {
    const targetMap = job.sourceWellTargetMap ?? {};
    // Build (compound::concLabel) → targetWells[] from the liquids rows
    const concToTargets = new Map<string, string[]>();
    for (const row of job.liquidsPreview) {
      const sourceWell = String(row["Source Well"] ?? "");
      if (!sourceWell) continue;
      const compound = String(row["compound"] ?? "");
      const rawStock = row["stock_mM"];
      const parsed = typeof rawStock === "number" ? rawStock : parseFloat(String(rawStock));
      const isControlLiquid = Boolean(row["is_control_liquid"]) || (!isNaN(parsed) && parsed === 0);
      const stockMM = isControlLiquid ? null : (isNaN(parsed) ? null : parsed);
      const concLabel = stockMM === null ? "No concentration" : String(stockMM);
      const key = `${compound}::${concLabel}`;
      if (!concToTargets.has(key)) {
        concToTargets.set(key, targetMap[sourceWell] ?? []);
      }
    }
    const MAX_SHOWN = 20;
    return (compound: string, concLabel: string): ReactNode | null => {
      const targets = concToTargets.get(`${compound}::${concLabel}`);
      if (!targets?.length) return null;
      return (
        <>
          <span className="well-tt-label">Target wells ({targets.length}) — </span>
          <span className="info-conc-extras-wells">
            {targets.slice(0, MAX_SHOWN).join(", ")}
            {targets.length > MAX_SHOWN && <> +{targets.length - MAX_SHOWN} more</>}
          </span>
        </>
      );
    };
  }, [job.liquidsPreview, job.sourceWellTargetMap]);

  if (!sourcePlatePreview) return null;

  return (
    <PlateGrid
      preview={sourcePlatePreview}
      title="Source plate layout"
      plateDef={plateDef}
      concentrationUnit="mM"
      wellTooltipContent={wellTooltipContent}
      concBlockExtras={concBlockExtras}
    />
  );
}
