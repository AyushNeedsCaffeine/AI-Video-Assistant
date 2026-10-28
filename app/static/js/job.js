(() => {
  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-copy-target]");
    if (!button) return;
    const target = document.getElementById(button.dataset.copyTarget);
    if (!target) return;
    const original = button.textContent;
    try {
      await navigator.clipboard.writeText(target.innerText);
      button.textContent = "Copied";
    } catch (error) {
      button.textContent = "Copy failed";
    }
    window.setTimeout(() => {
      button.textContent = original;
    }, 1600);
  });

  document.addEventListener("keydown", (event) => {
    if (!(event.target instanceof Element)) return;
    const textarea = event.target.closest("#message");
    if (!textarea) return;
    if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
    event.preventDefault();
    const form = textarea.form;
    if (form && !form.classList.contains("htmx-request")) form.requestSubmit();
  });

  const scrollChat = () => {
    const scroller = document.getElementById("chat-scroll");
    if (scroller) scroller.scrollTop = scroller.scrollHeight;
  };

  scrollChat();

  document.body.addEventListener("htmx:afterSwap", (event) => {
    if (event.detail && event.detail.target && event.detail.target.id === "chat-panel") {
      scrollChat();
    }
  });

  const root = document.getElementById("job-progress");
  if (!root) return;

  const jobId = root.dataset.jobId;
  const bar = document.getElementById("job-bar");
  const percent = document.getElementById("job-percent");
  const message = document.getElementById("job-message");
  const stageItems = Array.from(root.querySelectorAll("[data-stage]"));
  const stageOrder = stageItems.map((item) => item.dataset.stage);
  let reloading = false;
  let source = null;

  const setStage = (stage) => {
    const index = stageOrder.indexOf(stage);
    stageItems.forEach((item, itemIndex) => {
      item.classList.remove("is-done", "is-active", "is-pending");
      if (stage === "done" || (index > -1 && itemIndex < index)) {
        item.classList.add("is-done");
      } else if (itemIndex === index) {
        item.classList.add("is-active");
      } else {
        item.classList.add("is-pending");
      }
    });
  };

  const apply = (data) => {
    const progress = Math.max(0, Math.min(100, Number(data.progress) || 0));
    if (bar) bar.style.width = `${progress}%`;
    if (percent) percent.textContent = `${progress}%`;
    const track = bar ? bar.parentElement : null;
    if (track) track.setAttribute("aria-valuenow", String(progress));
    if (message) {
      message.textContent = data.status === "error" ? (data.error || "Processing failed") : (data.message || "");
    }
    if (data.stage) {
      root.dataset.stage = data.stage;
      setStage(data.stage);
    }
    if (bar) {
      if (data.status === "error") {
        bar.classList.add("is-stalled");
      } else {
        bar.classList.remove("is-stalled");
      }
    }
  };

  const finish = (data) => {
    apply(data);
    if (data.status === "complete" || data.status === "error") {
      if (source) source.close();
      if (!reloading) {
        reloading = true;
        window.setTimeout(() => window.location.reload(), 800);
      }
    }
  };

  if (!window.EventSource) {
    const poll = async () => {
      try {
        const response = await fetch(`/api/jobs/${jobId}`, { headers: { Accept: "application/json" } });
        if (!response.ok) throw new Error("status request failed");
        finish(await response.json());
        if (!reloading) window.setTimeout(poll, 1200);
      } catch (error) {
        if (bar) bar.classList.add("is-stalled");
        window.setTimeout(poll, 2500);
      }
    };
    poll();
    return;
  }

  source = new EventSource(`/jobs/${jobId}/events`);
  source.onmessage = (event) => {
    try {
      finish(JSON.parse(event.data));
    } catch (error) {
      if (bar) bar.classList.add("is-stalled");
    }
  };
  source.onerror = () => {
    if (!reloading && bar) bar.classList.add("is-stalled");
  };
})();
