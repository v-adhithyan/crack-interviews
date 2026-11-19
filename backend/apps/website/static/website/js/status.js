async function checkService(service) {
    const result = service.querySelector(".status-result");
    result.textContent = "Checking…";
    let operational = false;
    try {
        const response = await fetch(service.dataset.healthUrl, {
            headers: { Accept: "application/json" },
            credentials: "omit",
            cache: "no-store",
            redirect: "error",
            signal: AbortSignal.timeout(5000),
        });
        operational = response.ok && (await response.json())?.status === "ok";
    } catch {
        // A failed request or invalid response cannot verify reachability.
    }
    result.dataset.operational = operational;
    result.textContent = operational ? "Operational" : "Not reachable";
    return operational;
}

async function updateStatus() {
    const summary = document.querySelector("#status-summary");
    summary.textContent = "Checking service status…";

    const services = document.querySelectorAll("[data-health-url]");
    const results = await Promise.all(Array.from(services, checkService));
    const reachable = results.filter(Boolean).length;
    summary.textContent = `${reachable} of ${results.length} services reachable`;
    summary.dataset.operational = reachable === results.length;

    const checked = document.querySelector("#status-checked");
    const timestamp = checked.querySelector("time");
    const now = new Date();
    timestamp.dateTime = now.toISOString();
    timestamp.textContent = new Intl.DateTimeFormat(undefined, {
        year: "numeric", month: "short", day: "numeric",
        hour: "numeric", minute: "2-digit", timeZoneName: "short",
    }).format(now);
    checked.hidden = false;
}

updateStatus();
