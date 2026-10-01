(() => {
  const poller = document.querySelector("[data-page-poller]");
  if (!poller) return;

  let timeoutId = null;
  let requestInFlight = false;

  const schedule = () => {
    window.clearTimeout(timeoutId);
    if (poller.dataset.pollActive !== "true") return;
    timeoutId = window.setTimeout(refresh, Number(poller.dataset.pollInterval));
  };

  const refresh = async () => {
    if (requestInFlight || document.hidden || document.querySelector(".modal.show")) {
      schedule();
      return;
    }

    requestInFlight = true;
    try {
      const response = await fetch(window.location.href, {
        headers: {"X-Requested-With": "XMLHttpRequest"},
        cache: "no-store"
      });
      if (!response.ok) throw new Error(`Polling failed: ${response.status}`);

      const nextDocument = new DOMParser().parseFromString(
        await response.text(),
        "text/html"
      );

      document.querySelectorAll("[data-poll-region]").forEach((region) => {
        const key = region.dataset.pollRegion;
        const replacement = Array.from(
          nextDocument.querySelectorAll("[data-poll-region]")
        ).find((candidate) => candidate.dataset.pollRegion === key);
        if (replacement) region.replaceWith(replacement);
      });

      const nextPoller = nextDocument.querySelector("[data-page-poller]");
      poller.dataset.pollActive = nextPoller?.dataset.pollActive ?? "false";
      document.dispatchEvent(new CustomEvent("page:poll", {
        detail: {document: nextDocument}
      }));
    } catch (error) {
      console.error(error);
    } finally {
      requestInFlight = false;
      schedule();
    }
  };

  window.refreshPageRegions = refresh;
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refresh();
  });
  schedule();
})();
