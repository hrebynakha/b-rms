(() => {
  const modalElement = document.getElementById("confirmationModal");
  if (!modalElement) return;

  const modal = new bootstrap.Modal(modalElement);
  const titleElement = document.getElementById("confirmationModalTitle");
  const messageElement = document.getElementById("confirmationModalMessage");
  const confirmButton = document.getElementById("confirmationModalConfirm");
  const iconElement = document.getElementById("confirmationModalIcon");
  let resolveConfirmation = null;

  modalElement.addEventListener("hidden.bs.modal", () => {
    if (resolveConfirmation) resolveConfirmation(false);
    resolveConfirmation = null;
  });

  confirmButton.addEventListener("click", () => {
    const resolve = resolveConfirmation;
    resolveConfirmation = null;
    modal.hide();
    if (resolve) resolve(true);
  });

  window.confirmAction = (message, options = {}) => new Promise((resolve) => {
    if (resolveConfirmation) resolveConfirmation(false);
    resolveConfirmation = resolve;
    titleElement.textContent = options.title || modalElement.dataset.defaultTitle || "Confirm action";
    messageElement.textContent = message;
    confirmButton.textContent = options.confirmLabel || modalElement.dataset.defaultConfirm || "Confirm";
    const isWarning = options.tone === "warning";
    confirmButton.className = `btn ${isWarning ? "btn-warning" : "btn-danger"}`;
    iconElement.className = `modal-icon ${isWarning ? "modal-icon-warning" : "modal-icon-danger"}`;
    modal.show();
  });

  document.addEventListener("submit", async (event) => {
    const form = event.target.closest("form[data-confirm-message]");
    if (!form || form.dataset.confirmBypass === "true") return;
    event.preventDefault();
    const confirmed = await window.confirmAction(form.dataset.confirmMessage, {
      title: form.dataset.confirmTitle,
      confirmLabel: form.dataset.confirmLabel,
      tone: form.dataset.confirmTone
    });
    if (!confirmed) return;
    form.dataset.confirmBypass = "true";
    form.requestSubmit(event.submitter);
  });
})();
