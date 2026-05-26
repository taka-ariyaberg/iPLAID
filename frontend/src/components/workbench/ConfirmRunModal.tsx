import type { SolventFamily } from "../../types";
import "./ConfirmRunModal.css";

type ConfirmRunModalProps = {
  hasEdits: boolean;
  isEditMode: boolean;
  sourceLayoutFileName?: string | null;
  sourcePlateType?: string;
  solventFamilies: SolventFamily[];
  solventCaps?: Record<string, number> | null;
  onConfirm: () => void;
  onClose: () => void;
};

export function ConfirmRunModal({
  hasEdits,
  isEditMode,
  sourceLayoutFileName,
  sourcePlateType,
  solventFamilies,
  solventCaps,
  onConfirm,
  onClose,
}: ConfirmRunModalProps) {
  return (
    <div className="confirm-modal-backdrop" onClick={onClose}>
      <div className="confirm-modal" onClick={(e) => e.stopPropagation()}>
        <div className="confirm-modal-header">
          <h3>Start iPLAID run</h3>
        </div>
        <div className="confirm-modal-body">
          {isEditMode && (
            <p className="confirm-modal-warning">
              ⚠ Exit edit mode before starting a run — save or revert your changes first.
            </p>
          )}
          {hasEdits && !isEditMode && (
            <p className="confirm-modal-info">
              iPLAID will process your <strong>edited layout</strong>.
            </p>
          )}
          {!hasEdits && !isEditMode && (
            <p className="confirm-modal-info">
              iPLAID will process the <strong>original layout</strong>.
            </p>
          )}
          <div className="confirm-modal-source">
            <span className="confirm-modal-source-label">Source plate layout</span>
            {sourceLayoutFileName ? (
              <>
                <strong>{sourceLayoutFileName}</strong>
                <p>
                  This uploaded CSV will be used as the source of truth for source
                  plate wells{sourcePlateType ? ` on ${sourcePlateType}` : ""}.
                  The result artifact will summarize source plate usage instead
                  of generating preparation instructions.
                </p>
              </>
            ) : (
              <p>
                No source plate layout uploaded. iPLAID will assign source wells
                and generate source preparation output when supported.
              </p>
            )}
          </div>
          {solventFamilies.length > 0 && (
            <div className="confirm-solvent-caps">
              <p className="confirm-solvent-caps-title">
                Solvent caps (% of final well volume)
              </p>
              <ul>
                {solventFamilies.map((f) => {
                  const set = solventCaps?.[f.solventKey];
                  const isDefault = set === undefined || set === f.defaultCapPct;
                  const value = set ?? f.defaultCapPct;
                  return (
                    <li key={f.solventKey}>
                      {f.solvent}: {value}% {isDefault ? "(default)" : "(set)"}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>
        <div className="confirm-modal-footer">
          <button type="button" className="confirm-modal-cancel" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="confirm-modal-confirm"
            disabled={isEditMode}
            onClick={onConfirm}
          >
            Confirm &amp; start
          </button>
        </div>
      </div>
    </div>
  );
}
