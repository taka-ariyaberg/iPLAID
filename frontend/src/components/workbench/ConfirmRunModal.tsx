import "./ConfirmRunModal.css";

type ConfirmRunModalProps = {
  hasEdits: boolean;
  isEditMode: boolean;
  onConfirm: () => void;
  onClose: () => void;
};

export function ConfirmRunModal({ hasEdits, isEditMode, onConfirm, onClose }: ConfirmRunModalProps) {
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
