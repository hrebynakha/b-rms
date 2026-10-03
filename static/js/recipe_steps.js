(() => {
    const container = document.getElementById("steps-container");
    const status = document.getElementById("step-reorder-status");
    let drag = null;

    function announce(item) {
        updateStepNumbers();
        status.textContent = `${stepLabel} ${item.querySelector(".step-number").textContent}`;
    }

    function finish(cancelled = false) {
        if (!drag) return;
        const {item, handle, pointerId, originalOrder, frame, placeholder, originalStyle} = drag;
        drag = null;
        cancelAnimationFrame(frame);
        if (cancelled) originalOrder.forEach(step => container.append(step));
        placeholder.remove();
        item.classList.remove("is-dragging");
        if (originalStyle === null) item.removeAttribute("style");
        else item.setAttribute("style", originalStyle);
        if (container.hasPointerCapture(pointerId)) container.releasePointerCapture(pointerId);
        handle.focus({preventScroll: true});
        announce(item);
    }

    function move() {
        if (!drag) return;
        const {item, placeholder, x, y, offsetX, offsetY} = drag;
        item.style.left = `${x - offsetX}px`;
        item.style.top = `${y - offsetY}px`;
        const siblings = [...container.querySelectorAll(".step-item")].filter(step => step !== item);
        const next = siblings.find(step => {
            const rect = step.getBoundingClientRect();
            return y < rect.top + rect.height / 2;
        });
        if (placeholder.nextElementSibling !== (next || null)) {
            container.insertBefore(placeholder, next || null);
            container.insertBefore(item, placeholder);
            updateStepNumbers();
        }
        // Continue scrolling while the pointer stays near the viewport edge.
        if (y < 100) window.scrollBy(0, -12);
        else if (y > window.innerHeight - 80) window.scrollBy(0, 12);
        drag.frame = requestAnimationFrame(move);
    }

    container.addEventListener("pointerdown", event => {
        const handle = event.target.closest(".step-handle");
        if (!handle || handle.disabled || !event.isPrimary || event.button !== 0 || drag) return;
        if (container.children.length < 2) return;
        event.preventDefault();
        handle.focus({preventScroll: true});
        const item = handle.closest(".step-item");
        const rect = item.getBoundingClientRect();
        const originalOrder = [...container.querySelectorAll(".step-item")];
        const placeholder = document.createElement("div");
        placeholder.className = "step-placeholder";
        placeholder.setAttribute("aria-hidden", "true");
        placeholder.textContent = container.dataset.dropLabel;
        placeholder.style.height = `${rect.height}px`;
        placeholder.style.marginBottom = window.getComputedStyle(item).marginBottom;
        const originalStyle = item.getAttribute("style");
        container.insertBefore(placeholder, item);
        Object.assign(item.style, {
            position: "fixed", left: `${rect.left}px`, top: `${rect.top}px`,
            width: `${rect.width}px`, height: `${rect.height}px`, margin: "0",
        });
        drag = {
            item, handle, placeholder, originalStyle, originalOrder,
            pointerId: event.pointerId, x: event.clientX, y: event.clientY,
            offsetX: event.clientX - rect.left, offsetY: event.clientY - rect.top,
            frame: null,
        };
        // Capture on the stable container: moving a captured handle's card in
        // the DOM releases capture and cancels the drag in browsers.
        container.setPointerCapture(event.pointerId);
        item.classList.add("is-dragging");
        drag.frame = requestAnimationFrame(move);
    });

    container.addEventListener("pointermove", event => {
        if (drag && event.pointerId === drag.pointerId) {
            drag.x = event.clientX;
            drag.y = event.clientY;
        }
    });
    container.addEventListener("pointerup", event => {
        if (drag && event.pointerId === drag.pointerId) {
            drag.x = event.clientX;
            drag.y = event.clientY;
            cancelAnimationFrame(drag.frame);
            move();
            finish();
        }
    });
    container.addEventListener("pointercancel", event => {
        if (drag && event.pointerId === drag.pointerId) finish(true);
    });
    container.addEventListener("lostpointercapture", event => {
        if (drag && event.pointerId === drag.pointerId) finish(true);
    });

    document.addEventListener("keydown", event => {
        if (drag && event.key === "Escape") {
            event.preventDefault();
            finish(true);
            return;
        }
        const handle = event.target.closest(".step-handle");
        if (!handle || handle.disabled || drag) return;
        const item = handle.closest(".step-item");
        if (event.key === "ArrowUp") {
            event.preventDefault();
            if (item.previousElementSibling) container.insertBefore(item, item.previousElementSibling);
        } else if (event.key === "ArrowDown") {
            event.preventDefault();
            if (item.nextElementSibling) container.insertBefore(item.nextElementSibling, item);
        } else return;
        handle.focus({preventScroll: true});
        item.scrollIntoView({block: "nearest", behavior: "instant"});
        announce(item);
    });
})();
