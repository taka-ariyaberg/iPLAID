import type { JobRecord } from "../../types";
import { parseLiquidName } from "../../utils/liquidUtils";
import "./SourceStocksTable.css";

type SourceStocksTableProps = {
  job: JobRecord;
};

export function SourceStocksTable({ job }: SourceStocksTableProps) {
  if (!job.liquidsPreview.length) return null;

  return (
    <section className="panel-surface data-table-panel">
      <div className="panel-header-row">
        <div>
          <p className="section-kicker">Source stocks</p>
          <h3>Well assignments &amp; usage</h3>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Compound</th>
              <th>Stock (mM)</th>
              <th>Source well</th>
              <th>Target wells</th>
            </tr>
          </thead>
          <tbody>
            {job.liquidsPreview.map((row, index) => {
              const liquidName = String(row["Liquid Name"] ?? "");
              const hasNewFormat = "compound" in row && "stock_mM" in row;
              const parsed = hasNewFormat ? null : parseLiquidName(liquidName);
              const compound = hasNewFormat ? String(row["compound"]) : (parsed?.compound ?? liquidName);
              const isDmso = compound.toUpperCase() === "DMSO";
              const stockMM = hasNewFormat
                ? (isDmso ? null : row["stock_mM"])
                : parsed?.stockMM;
              const stockMatch = job.stockSummary.find(
                (s) =>
                  String(s.cmpdname) === compound &&
                  (isDmso || Number(s.stock_conc_mM) === stockMM),
              );
              return (
                <tr key={`${index}-${liquidName}`}>
                  <td>{compound}</td>
                  <td>{stockMM != null ? `${stockMM} mM` : "—"}</td>
                  <td className="mono">{String(row["Source Well"] ?? "")}</td>
                  <td>{stockMatch != null ? String(stockMatch.count) : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
