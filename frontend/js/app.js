(function () {
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    let currentPage = "pipeline";
    let emails = [];
    let selectedEmailIds = new Set();
    let generatedArticles = [];
    let selectedArticleIds = new Set();
    let currentView = "cards";
    let sseController = null;
    let generationMode = "batch";

    // --- Logging ---
    function log(msg, type = "info") {
        const body = $("#logs-body");
        const entry = document.createElement("div");
        entry.className = `log-entry log-${type}`;
        entry.textContent = msg;
        body.appendChild(entry);
        body.scrollTop = body.scrollHeight;
    }

    function clearLogs() {
        $("#logs-body").innerHTML = "";
    }

    // --- Steps ---
    function enableStep(id) {
        const el = $(`#step-${id}`);
        if (el) el.classList.remove("disabled");
    }

    function disableStep(id) {
        const el = $(`#step-${id}`);
        if (el) el.classList.add("disabled");
    }

    // --- Auth ---
    async function checkAuth() {
        try {
            const auth = await API.getAuthStatus();
            const dot = $("#sidebar-auth-dot");
            const text = $("#sidebar-auth-text");
            if (auth.authenticated) {
                dot.className = "auth-dot online";
                text.textContent = "Gmail connected";
            } else {
                dot.className = "auth-dot offline";
                text.textContent = "Gmail not connected";
            }
            return auth.authenticated;
        } catch {
            return false;
        }
    }

    // --- Navigation ---
    function navigateTo(page) {
        currentPage = page;
        $$(".page").forEach((p) => p.classList.remove("active"));
        $(`#page-${page}`).classList.add("active");
        $$(".nav-link").forEach((l) => {
            l.classList.toggle("active", l.dataset.page === page);
        });
        if (page === "settings") loadSettings();
        if (page === "dashboard") loadDashboard();
    }

    // --- Fetch ---
    async function doFetch() {
        const btn = $("#btn-fetch");
        btn.disabled = true;
        btn.textContent = "Fetching...";

        try {
            log("Fetching emails from Gmail...", "progress");
            const result = await API.fetchEmails({
                max_results: parseInt($("#fetch-count").value) || 10,
                query: $("#fetch-query").value,
                mark_read: $("#fetch-mark-read").checked,
                add_label: $("#fetch-add-label").checked,
            });

            log(`Fetched ${result.fetched} emails (${result.new} new)`, "success");
            emails = result.emails || [];
            renderEmailList();
            enableStep("select");
            log(`Fetched ${result.new} new emails`, "success");
        } catch (e) {
            log("Fetch failed: " + e.message, "error");
            log("Fetch failed: " + e.message, "error");
        } finally {
            btn.disabled = false;
            btn.textContent = "Fetch Emails";
        }
    }

    // --- Email List ---
    let expandedEmailId = null;

    function renderEmailList() {
        const container = $("#email-list");
        if (emails.length === 0) {
            container.innerHTML = '<div class="empty-state">No emails to display.</div>';
            return;
        }
        container.innerHTML = emails
            .map(
                (e) => `
            <div class="email-wrap" data-id="${e.id}">
                <div class="email-item" data-id="${e.id}">
                    <input type="checkbox" class="email-item-check" data-id="${e.id}" ${
                        selectedEmailIds.has(e.id) ? "checked" : ""
                    }>
                    <div class="email-item-info">
                        <div class="email-item-title">${esc(e.title)}</div>
                        <div class="email-item-meta">
                            <span>${esc(e.sender)}</span>
                            <span>${esc(e.date)}</span>
                        </div>
                    </div>
                    <span class="email-expand-arrow">&#9660;</span>
                </div>
                <div class="email-details">
                    <div class="email-details-meta">
                        <span><strong>From:</strong> ${esc(e.sender)}</span>
                        <span><strong>Date:</strong> ${esc(e.date)}</span>
                    </div>
                    <div class="email-details-body">${esc(e.body) || "(no body)"}</div>
                    ${e.attachments && e.attachments.length > 0
                        ? `<div class="email-details-attachments"><strong>Attachments:</strong> ${e.attachments.map(a => `<span class="attachment-tag">${esc(a)}</span>`).join("")}</div>`
                        : ""}
                </div>
            </div>`
            )
            .join("");

        container.querySelectorAll(".email-item").forEach((el) => {
            el.addEventListener("click", (ev) => {
                if (ev.target.type === "checkbox") return;
                toggleEmailDetails(el.dataset.id);
            });
        });

        container.querySelectorAll(".email-item-check").forEach((cb) => {
            cb.addEventListener("change", () => {
                if (cb.checked) selectedEmailIds.add(cb.dataset.id);
                else selectedEmailIds.delete(cb.dataset.id);
                updateSelectionCount();
            });
        });

        updateSelectionCount();
    }

    function toggleEmailDetails(id) {
        const wrap = $(`.email-wrap[data-id="${id}"]`);
        if (!wrap) return;
        const details = wrap.querySelector(".email-details");
        const arrow = wrap.querySelector(".email-expand-arrow");

        if (expandedEmailId === id) {
            // collapse
            details.style.display = "none";
            wrap.classList.remove("expanded");
            expandedEmailId = null;
        } else {
            // collapse previous
            if (expandedEmailId) {
                const prev = $(`.email-wrap[data-id="${expandedEmailId}"]`);
                if (prev) {
                    prev.querySelector(".email-details").style.display = "none";
                    prev.classList.remove("expanded");
                }
            }
            // expand new
            details.style.display = "block";
            wrap.classList.add("expanded");
            expandedEmailId = id;
        }
    }

    function updateSelectionCount() {
        const count = selectedEmailIds.size;
        $("#selected-count").textContent = `${count} selected`;
        $("#btn-generate").disabled = count === 0;
        const allChecked = emails.length > 0 && count === emails.length;
        $("#select-all").checked = allChecked;

        const batchRadio = $('input[name="gen-mode"][value="batch"]');
        const singleRadio = $('input[name="gen-mode"][value="single"]');
        if (count <= 1) {
            batchRadio.disabled = true;
            singleRadio.checked = true;
        } else {
            batchRadio.disabled = false;
        }
    }

    // --- Generate (SSE) ---
    async function doGenerate() {
        const ids = Array.from(selectedEmailIds);
        if (ids.length === 0) return;

        const btn = $("#btn-generate");
        btn.disabled = true;
        btn.textContent = "Generating...";

        const mode = $('input[name="gen-mode"]:checked')?.value || "batch";
        generationMode = mode;

        generatedArticles = [];
        selectedArticleIds = new Set();

        enableStep("review");
        log(`Starting generation for ${ids.length} email(s) [${mode} mode]...`, "progress");

        sseController = API.generateStream(ids, mode, (event) => {
            switch (event.type) {
                case "batch_start":
                    log(`Generating ${event.count} article(s) in a single API call...`, "progress");
                    break;
                case "start":
                    log(`[${event.current}/${event.total}] Processing: ${event.title}`, "progress");
                    break;
                case "done":
                    log(`[${event.current}/${event.total}] Article generated: ${event.article.headline}`, "success");
                    generatedArticles.push(event.article);
                    selectedArticleIds.add(event.article.id);
                    break;
                case "error":
                    log(`[${event.current}/${event.total}] Error: ${event.message}`, "error");
                    break;
                case "complete":
                    log(`Generation complete. ${event.count} article(s) ready for review.`, "success");
                    renderArticles();
                    btn.disabled = false;
                    btn.textContent = "Generate Articles";
                    break;
                case "stream_error":
                    log("Stream error: " + event.message, "error");
                    btn.disabled = false;
                    btn.textContent = "Generate Articles";
                    break;
            }
        });
    }

    // --- Articles ---
    function renderArticles() {
        const count = generatedArticles.length;
        $("#review-count").textContent = `${count} article(s)`;
        renderArticleCards();
        renderArticleJSON();
        updateDraftButton();
    }

    function renderArticleCards() {
        const container = $("#article-list");
        if (generatedArticles.length === 0) {
            container.innerHTML = '<div class="empty-state">No articles generated yet.</div>';
            return;
        }
        container.innerHTML = generatedArticles
            .map(
                (a) => `
            <div class="article-card" data-id="${a.id}">
                <div class="article-card-header">
                    <input type="checkbox" class="article-check" data-id="${a.id}" ${
                        selectedArticleIds.has(a.id) ? "checked" : ""
                    }>
                    <input type="text" class="article-headline" data-id="${a.id}" value="${esc(a.headline)}">
                </div>
                <div class="article-seo-fields">
                    <div class="article-seo-row">
                        <label>SEO Title</label>
                        <input type="text" class="article-seo-title" data-id="${a.id}" value="${esc(a.seo_title || "")}" placeholder="SEO title (max 60 chars)">
                        <span class="article-seo-count" data-field="seo-title">${(a.seo_title || "").length}/60</span>
                    </div>
                    <div class="article-seo-row">
                        <label>SEO Description</label>
                        <input type="text" class="article-seo-desc" data-id="${a.id}" value="${esc(a.seo_description || "")}" placeholder="SEO description (max 160 chars)">
                        <span class="article-seo-count" data-field="seo-desc">${(a.seo_description || "").length}/160</span>
                    </div>
                </div>
                <div class="article-body-rendered" data-id="${a.id}">${a.body || "<p>(no body)</p>"}</div>
                <textarea class="article-body" data-id="${a.id}" style="display:none;">${esc(a.body)}</textarea>
                <div class="article-card-actions">
                    <button class="btn btn-small btn-secondary btn-edit-article" data-id="${a.id}">Edit</button>
                    <button class="btn btn-small btn-primary btn-save-article" data-id="${a.id}" style="display:none;">Save</button>
                    <button class="btn btn-small btn-secondary btn-cancel-article" data-id="${a.id}" style="display:none;">Cancel</button>
                </div>
                <div class="article-card-footer">
                    <span>${esc(a.filename)}</span>
                    <a href="${API.downloadArticleUrl(a.id)}" class="btn btn-small btn-secondary" target="_blank">Download</a>
                </div>
            </div>`
            )
            .join("");

        container.querySelectorAll(".article-check").forEach((cb) => {
            cb.addEventListener("change", () => {
                if (cb.checked) selectedArticleIds.add(cb.dataset.id);
                else selectedArticleIds.delete(cb.dataset.id);
                updateDraftButton();
            });
        });

        container.querySelectorAll(".article-headline").forEach((input) => {
            input.addEventListener("change", () => {
                const a = generatedArticles.find((x) => x.id === input.dataset.id);
                if (a) a.headline = input.value;
            });
        });

        container.querySelectorAll(".article-seo-title").forEach((input) => {
            input.addEventListener("input", () => {
                const a = generatedArticles.find((x) => x.id === input.dataset.id);
                if (a) a.seo_title = input.value;
                const counter = input.parentElement.querySelector(".article-seo-count");
                if (counter) counter.textContent = `${input.value.length}/60`;
            });
        });

        container.querySelectorAll(".article-seo-desc").forEach((input) => {
            input.addEventListener("input", () => {
                const a = generatedArticles.find((x) => x.id === input.dataset.id);
                if (a) a.seo_description = input.value;
                const counter = input.parentElement.querySelector(".article-seo-count");
                if (counter) counter.textContent = `${input.value.length}/160`;
            });
        });

        container.querySelectorAll(".btn-edit-article").forEach((btn) => {
            btn.addEventListener("click", () => {
                const id = btn.dataset.id;
                const card = container.querySelector(`.article-card[data-id="${id}"]`);
                card.querySelector(".article-body-rendered").style.display = "none";
                card.querySelector(".article-body").style.display = "block";
                btn.style.display = "none";
                card.querySelector(".btn-save-article").style.display = "inline-flex";
                card.querySelector(".btn-cancel-article").style.display = "inline-flex";
            });
        });

        container.querySelectorAll(".btn-save-article").forEach((btn) => {
            btn.addEventListener("click", () => {
                const id = btn.dataset.id;
                const card = container.querySelector(`.article-card[data-id="${id}"]`);
                const ta = card.querySelector(".article-body");
                const rendered = card.querySelector(".article-body-rendered");
                const a = generatedArticles.find((x) => x.id === id);
                if (a) a.body = ta.value;
                rendered.innerHTML = ta.value;
                rendered.style.display = "block";
                ta.style.display = "none";
                btn.style.display = "none";
                card.querySelector(".btn-cancel-article").style.display = "none";
                card.querySelector(".btn-edit-article").style.display = "inline-flex";
            });
        });

        container.querySelectorAll(".btn-cancel-article").forEach((btn) => {
            btn.addEventListener("click", () => {
                const id = btn.dataset.id;
                const card = container.querySelector(`.article-card[data-id="${id}"]`);
                const a = generatedArticles.find((x) => x.id === id);
                const ta = card.querySelector(".article-body");
                if (a) ta.value = a.body;
                card.querySelector(".article-body-rendered").style.display = "block";
                ta.style.display = "none";
                btn.style.display = "none";
                card.querySelector(".btn-save-article").style.display = "none";
                card.querySelector(".btn-edit-article").style.display = "inline-flex";
            });
        });

        container.querySelectorAll(".article-body").forEach((ta) => {
            ta.addEventListener("change", () => {
                const a = generatedArticles.find((x) => x.id === ta.dataset.id);
                if (a) a.body = ta.value;
            });
        });
    }

    function renderArticleJSON() {
        const container = $("#article-json");
        const data = generatedArticles.map((a) => ({
            id: a.id,
            email_id: a.email_id,
            headline: a.headline,
            body: a.body,
            filename: a.filename,
        }));
        container.textContent = JSON.stringify(data, null, 2);
    }

    function updateDraftButton() {
        const btn = $("#btn-create-drafts");
        btn.disabled = selectedArticleIds.size === 0;
        btn.textContent = `Create Drafts (${selectedArticleIds.size})`;
    }

    // --- Create Drafts ---
    async function doCreateDrafts() {
        const btn = $("#btn-create-drafts");
        btn.disabled = true;
        btn.textContent = "Creating drafts...";

        const articlesToSend = generatedArticles
            .filter((a) => selectedArticleIds.has(a.id))
            .map((a) => {
                const email = emails.find((e) => e.id === a.email_id) || {};
                return {
                    article_id: a.id,
                    headline: a.headline,
                    body: a.body,
                    seo_title: a.seo_title || "",
                    seo_description: a.seo_description || "",
                    email_id: a.email_id,
                    original_title: email.title || "",
                    original_sender: email.sender || "",
                };
            });

        log(`Creating ${articlesToSend.length} Gmail draft(s)...`, "progress");

        try {
            const result = await API.createDrafts(articlesToSend);
            let ok = 0;
            let fail = 0;
            for (const r of result.results) {
                if (r.status === "ok") {
                    ok++;
                    log(`Draft created: ${r.draft_id}`, "success");
                } else {
                    fail++;
                    log(`Draft failed for ${r.article_id}: ${r.error}`, "error");
                }
            }
            log(`Done. ${ok} draft(s) created, ${fail} failed.`, ok > 0 ? "success" : "error");
        } catch (e) {
            log("Draft creation failed: " + e.message, "error");
        } finally {
            btn.disabled = false;
            updateDraftButton();
        }
    }

    // --- Settings ---
    async function loadSettings() {
        try {
            const [settings, auth] = await Promise.all([API.getSettings(), API.getAuthStatus()]);
            const authEl = $("#auth-status-display");
            if (auth.authenticated) {
                const email = auth.email ? ` as <strong>${auth.email}</strong>` : "";
                authEl.innerHTML = `<span class="connected">Connected to Gmail${email}</span>`;
            } else {
                authEl.innerHTML = '<span class="disconnected">Not connected</span>';
            }

            // AI provider selection
            const providerRadios = $$('input[name="ai-provider"]');
            providerRadios.forEach((r) => {
                r.checked = r.value === settings.ai_provider;
            });

            // Provider status badges
            if (settings.providers) {
                for (const [name, info] of Object.entries(settings.providers)) {
                    const statusEl = $(`#${name}-status`);
                    if (statusEl) {
                        if (info.configured) {
                            statusEl.textContent = "API key configured";
                            statusEl.className = "ai-provider-status configured";
                        } else {
                            statusEl.textContent = "Not configured";
                            statusEl.className = "ai-provider-status not-configured";
                        }
                    }
                }
            }

            loadCredentialsStatus();
            loadIgnoredSenders();
            loadArticleSettings();

            // System rules
            if (settings.system_rules !== undefined) {
                $("#system-rules-textarea").value = settings.system_rules;
            }
        } catch (e) {
            log("Failed to load settings: " + e.message, "error");
        }
    }

    // --- Article Settings ---
    async function loadArticleSettings() {
        try {
            const s = await API.getArticleSettings();
            $("#art-min-words").value = s.min_words ?? 50;
            $("#art-max-words").value = s.max_words ?? 200;
            $("#art-language").value = s.language ?? "polish";
            $("#art-default-mode").value = s.default_mode ?? "batch";
            // Apply default mode to pipeline toggle
            const modeRadio = $(`input[name="gen-mode"][value="${s.default_mode || 'batch'}"]`);
            if (modeRadio) modeRadio.checked = true;
        } catch (e) {
            log("Failed to load article settings: " + e.message, "error");
        }
    }

    // --- Credentials Upload ---
    let selectedCredentialFile = null;

    async function loadCredentialsStatus() {
        try {
            const result = await API.getCredentialsStatus();
            const el = $("#credentials-status");
            if (result.exists) {
                el.innerHTML = `<span class="connected">Credentials file found</span> <span class="text-muted small">(${esc(result.type || "JSON")})</span>`;
            } else {
                el.innerHTML = '<span class="disconnected">No credentials file found</span>';
            }
        } catch (e) {
            log("Failed to check credentials: " + e.message, "error");
        }
    }

    async function uploadCredentials() {
        const btn = $("#btn-save-credentials");
        if (!selectedCredentialFile) return;

        btn.disabled = true;
        btn.textContent = "Uploading...";

        try {
            await API.uploadCredentials(selectedCredentialFile);
            log("Credentials uploaded successfully!", "success");
            selectedCredentialFile = null;
            $("#credentials-file-name").textContent = "No file selected";
            btn.disabled = true;
            loadCredentialsStatus();
        } catch (e) {
            log("Upload failed: " + e.message, "error");
        } finally {
            btn.disabled = false;
            btn.textContent = "Upload & Save";
        }
    }

    let ignoredSenders = [];

    async function loadIgnoredSenders() {
        try {
            const result = await API.getIgnoredSenders();
            ignoredSenders = result.senders || [];
            renderIgnoredSenders();
        } catch (e) {
            log("Failed to load ignored senders: " + e.message, "error");
        }
    }

    function renderIgnoredSenders() {
        const container = $("#ignored-senders-list");
        if (ignoredSenders.length === 0) {
            container.innerHTML = '<div class="ignored-empty">No ignored senders yet.</div>';
            return;
        }
        container.innerHTML = ignoredSenders
            .map(
                (s) => `
            <div class="ignored-sender-item">
                <span>${esc(s)}</span>
                <button class="btn-remove-ignored" data-sender="${esc(s)}" title="Remove">&times;</button>
            </div>`
            )
            .join("");

        container.querySelectorAll(".btn-remove-ignored").forEach((btn) => {
            btn.addEventListener("click", async () => {
                const sender = btn.dataset.sender;
                try {
                    await API.removeIgnoredSender(sender);
                    log(`Removed "${sender}" from ignore list`, "success");
                    loadIgnoredSenders();
                } catch (e) {
                    log("Failed to remove: " + e.message, "error");
                }
            });
        });
    }

    async function addIgnoredSender() {
        const input = $("#ignored-sender-input");
        const sender = input.value.trim();
        if (!sender) return;

        try {
            await API.addIgnoredSender(sender);
            input.value = "";
            log(`"${sender}" added to ignore list`, "success");
            loadIgnoredSenders();
        } catch (e) {
            log("Failed to add: " + e.message, "error");
        }
    }

    // --- Dashboard ---
    async function loadDashboard() {
        try {
            const [summary, quota] = await Promise.all([
                API.getUsageSummary(""),
                API.getQuota(),
            ]);

            // Summary cards
            $("#dash-today-requests").textContent = summary.today_requests;
            $("#dash-week-requests").textContent = summary.week_requests;
            $("#dash-month-requests").textContent = summary.month_requests;
            $("#dash-total-requests").textContent = summary.total_requests;
            $("#dash-today-tokens").textContent = formatTokens(summary.today_tokens);
            $("#dash-week-tokens").textContent = formatTokens(summary.week_tokens);
            $("#dash-month-tokens").textContent = formatTokens(summary.month_tokens);
            $("#dash-avg-latency").textContent = summary.avg_latency_ms;
            $("#dash-total-success").textContent = summary.total_success;
            $("#dash-total-fail").textContent = summary.total_fail;

            // Quota bars
            updateQuotaBar("daily-req", summary.today_requests, quota.daily_requests);
            updateQuotaBar("weekly-req", summary.week_requests, quota.weekly_requests);
            updateQuotaBar("monthly-req", summary.month_requests, quota.monthly_requests);
            updateQuotaBar("daily-tok", summary.today_tokens, quota.daily_tokens);
            updateQuotaBar("weekly-tok", summary.week_tokens, quota.weekly_tokens);
            updateQuotaBar("monthly-tok", summary.month_tokens, quota.monthly_tokens);

            // Quota form
            $("#quota-input-daily-requests").value = quota.daily_requests || 0;
            $("#quota-input-weekly-requests").value = quota.weekly_requests || 0;
            $("#quota-input-monthly-requests").value = quota.monthly_requests || 0;
            $("#quota-input-daily-tokens").value = quota.daily_tokens || 0;
            $("#quota-input-weekly-tokens").value = quota.weekly_tokens || 0;
            $("#quota-input-monthly-tokens").value = quota.monthly_tokens || 0;

            // Reset times
            const resets = summary.resets_in || {};
            if (resets.daily) $("#quota-daily-reset").textContent = "resets in " + resets.daily;
            if (resets.weekly) $("#quota-weekly-reset").textContent = "resets in " + resets.weekly;
            if (resets.monthly) $("#quota-monthly-reset").textContent = "resets in " + resets.monthly;

            // By provider
            const providerEl = $("#dash-by-provider");
            const providers = summary.by_provider || {};
            const activeProvider = (await API.getSettings()).ai_provider;
            if (Object.keys(providers).length === 0) {
                providerEl.innerHTML = '<div class="text-muted" style="padding:8px 0;">No API calls yet.</div>';
            } else {
                providerEl.innerHTML = Object.entries(providers)
                    .map(
                        ([name, stats]) => `
                    <div class="dash-provider-item">
                        <span class="provider-name">${esc(name)}</span>
                        <span class="provider-stats">${stats.requests} req / ${formatTokens(stats.tokens)} tokens / ${stats.fail} fail</span>
                        ${name === activeProvider ? '<span class="provider-active">ACTIVE</span>' : ""}
                    </div>`
                    )
                    .join("");
            }

            // Recent activity
            const records = (await API.getUsage("", "", 50)).records || [];
            const tbody = $("#dash-recent-body");
            if (records.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="text-muted" style="text-align:center;padding:16px;">No activity yet.</td></tr>';
            } else {
                tbody.innerHTML = records
                    .reverse()
                    .map(
                        (r) => `
                    <tr>
                        <td>${formatTime(r.ts)}</td>
                        <td>${esc(r.provider)}</td>
                        <td>${esc(r.operation)}</td>
                        <td>${r.input_tokens + r.output_tokens > 0 ? formatTokens(r.input_tokens + r.output_tokens) : "-"}</td>
                        <td>${r.latency_ms > 0 ? r.latency_ms + "ms" : "-"}</td>
                        <td class="${r.success ? "status-ok" : "status-fail"}">${r.success ? "OK" : "FAIL"}</td>
                    </tr>`
                    )
                    .join("");
            }
        } catch (e) {
            log("Failed to load dashboard: " + e.message, "error");
        }
    }

    function formatTokens(n) {
        if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
        if (n >= 1000) return (n / 1000).toFixed(1) + "k";
        return String(n);
    }

    function formatTime(iso) {
        try {
            const d = new Date(iso);
            return d.toLocaleString("pl-PL", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
        } catch {
            return iso;
        }
    }

    function updateQuotaBar(prefix, current, limit) {
        const bar = $(`#quota-${prefix}-bar`);
        const text = $(`#quota-${prefix}-text`);
        if (!bar || !text) return;
        if (!limit || limit <= 0) {
            bar.style.width = "0%";
            bar.className = "quota-bar-fill";
            text.textContent = `${current} / unlimited`;
            return;
        }
        const pct = Math.min(100, Math.round((current / limit) * 100));
        bar.style.width = pct + "%";
        bar.className = "quota-bar-fill" + (pct >= 100 ? " over" : pct >= 80 ? " warn" : "");
        text.textContent = `${current} / ${limit}`;
    }

    function esc(str) {
        const div = document.createElement("div");
        div.textContent = str || "";
        return div.innerHTML;
    }

    // --- Event Listeners ---
    $$(".nav-link").forEach((link) => {
        link.addEventListener("click", (e) => {
            e.preventDefault();
            navigateTo(link.dataset.page);
        });
    });

    $("#btn-fetch").addEventListener("click", doFetch);
    $("#btn-generate").addEventListener("click", doGenerate);
    $("#btn-create-drafts").addEventListener("click", doCreateDrafts);
    $("#btn-clear-logs").addEventListener("click", clearLogs);

    // --- Mode Info Modal ---
    $("#btn-mode-info").addEventListener("click", () => {
        $("#modal-mode-info").style.display = "flex";
    });
    $("#btn-close-modal").addEventListener("click", () => {
        $("#modal-mode-info").style.display = "none";
    });
    $("#modal-mode-info").addEventListener("click", (e) => {
        if (e.target === e.currentTarget) {
            $("#modal-mode-info").style.display = "none";
        }
    });

    $("#select-all").addEventListener("change", (e) => {
        const checked = e.target.checked;
        selectedEmailIds.clear();
        if (checked) emails.forEach((em) => selectedEmailIds.add(em.id));
        renderEmailList();
    });

    $("#review-select-all").addEventListener("change", (e) => {
        const checked = e.target.checked;
        selectedArticleIds.clear();
        if (checked) generatedArticles.forEach((a) => selectedArticleIds.add(a.id));
        renderArticleCards();
        updateDraftButton();
    });

    $$(".view-toggle .btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            $$(".view-toggle .btn").forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            currentView = btn.dataset.view;
            $("#article-list").style.display = currentView === "cards" ? "flex" : "none";
            $("#article-json").style.display = currentView === "json" ? "block" : "none";
        });
    });


    $("#btn-connect-gmail").addEventListener("click", async () => {
        try {
            log("Starting Gmail authentication...", "info");
            const result = await API.startAuth();
            if (result.success) {
                log("Gmail connected!", "success");
            } else {
                log("Auth failed: " + (result.error || "unknown"), "error");
            }
            loadSettings();
            checkAuth();
        } catch (e) {
            log("Auth error: " + e.message, "error");
        }
    });

    $("#btn-add-ignored").addEventListener("click", addIgnoredSender);
    $("#ignored-sender-input").addEventListener("keydown", (e) => {
        if (e.key === "Enter") addIgnoredSender();
    });

    // --- Credentials Upload ---
    $("#btn-upload-credentials").addEventListener("click", () => {
        $("#credentials-file-input").click();
    });

    $("#credentials-file-input").addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (file) {
            selectedCredentialFile = file;
            $("#credentials-file-name").textContent = file.name;
            $("#btn-save-credentials").disabled = false;
        }
    });

    $("#btn-save-credentials").addEventListener("click", uploadCredentials);

    // --- AI Provider ---
    $("#btn-save-provider").addEventListener("click", async () => {
        const selected = $('input[name="ai-provider"]:checked');
        if (!selected) {
            log("Please select a provider", "error");
            return;
        }
        try {
            await API.setAIProvider(selected.value);
            log(`AI provider set to ${selected.value}`, "success");
            loadSettings();
        } catch (e) {
            log("Failed to save provider: " + e.message, "error");
        }
    });

    // --- System Rules ---
    $("#btn-save-system-rules").addEventListener("click", async () => {
        const rules = $("#system-rules-textarea").value.trim();
        if (!rules) {
            log("System prompt cannot be empty", "error");
            return;
        }
        try {
            await API.setSystemRules(rules);
            log("System prompt saved", "success");
        } catch (e) {
            log("Failed to save prompt: " + e.message, "error");
        }
    });

    // --- Article Settings ---
    $("#btn-save-article-settings").addEventListener("click", async () => {
        const minWords = parseInt($("#art-min-words").value) || 0;
        const maxWords = parseInt($("#art-max-words").value) || 200;
        const language = $("#art-language").value;
        const defaultMode = $("#art-default-mode").value;

        if (minWords > maxWords) {
            log("Min words cannot exceed max words", "error");
            return;
        }
        try {
            await API.setArticleSettings({
                min_words: minWords,
                max_words: maxWords,
                language: language,
                default_mode: defaultMode,
            });
            // Apply default mode to pipeline
            const modeRadio = $(`input[name="gen-mode"][value="${defaultMode}"]`);
            if (modeRadio) modeRadio.checked = true;
            log("Article settings saved", "success");
        } catch (e) {
            log("Failed to save article settings: " + e.message, "error");
        }
    });

    // --- API Key Save Buttons ---
    $$('[data-action="save-key"]').forEach((btn) => {
        btn.addEventListener("click", async () => {
            const provider = btn.dataset.provider;
            const input = $(`#${provider}-key-input`);
            const key = input.value.trim();
            if (!key) {
                log("Please enter an API key", "error");
                return;
            }
            try {
                await API.setAPIKey(key, provider);
                log(`${provider} API key saved`, "success");
                input.value = "";
                loadSettings();
            } catch (e) {
                log("Failed to save key: " + e.message, "error");
            }
        });
    });

    // --- API Key Test Buttons ---
    $$('[data-action="test-key"]').forEach((btn) => {
        btn.addEventListener("click", async () => {
            const provider = btn.dataset.provider;
            const resultEl = $(`#${provider}-test-result`);
            btn.disabled = true;
            btn.textContent = "...";
            resultEl.textContent = "";
            resultEl.className = "ai-provider-test-result";

            try {
                const result = await API.testAPIKey(provider);
                if (result.ok) {
                    resultEl.textContent = `Connected. Model: ${result.model}`;
                    resultEl.className = "ai-provider-test-result test-ok";
                } else {
                    resultEl.textContent = result.error || "Connection failed";
                    resultEl.className = "ai-provider-test-result test-fail";
                }
            } catch (e) {
                resultEl.textContent = "Test failed: " + e.message;
                resultEl.className = "ai-provider-test-result test-fail";
            } finally {
                btn.disabled = false;
                btn.textContent = "Test";
            }
        });
    });

    // --- Quota & Reset ---
    $("#btn-save-quota").addEventListener("click", async () => {
        const quota = {
            daily_requests: parseInt($("#quota-input-daily-requests").value) || 0,
            weekly_requests: parseInt($("#quota-input-weekly-requests").value) || 0,
            monthly_requests: parseInt($("#quota-input-monthly-requests").value) || 0,
            daily_tokens: parseInt($("#quota-input-daily-tokens").value) || 0,
            weekly_tokens: parseInt($("#quota-input-weekly-tokens").value) || 0,
            monthly_tokens: parseInt($("#quota-input-monthly-tokens").value) || 0,
        };
        try {
            await API.setQuota(quota);
            log("Quota limits saved", "success");
            loadDashboard();
        } catch (e) {
            log("Failed to save quota: " + e.message, "error");
        }
    });

    $("#btn-reset-usage").addEventListener("click", async () => {
        if (!confirm("Reset all usage data? This cannot be undone.")) return;
        try {
            await API.resetUsage();
            log("Usage data reset", "success");
            loadDashboard();
        } catch (e) {
            log("Failed to reset usage: " + e.message, "error");
        }
    });

    // --- Getting Started: Accordion & Search ---
    function initGettingStarted() {
        const accordions = $$('#page-getting-started .gs-accordion');
        const searchInput = $('#gs-search-input');
        const searchClear = $('#gs-search-clear');
        const searchResults = $('#gs-search-results');
        const tocLinks = $$('#gs-toc .gs-toc-link');

        if (!searchInput || accordions.length === 0) return;

        // Accordion toggle
        accordions.forEach(acc => {
            const header = acc.querySelector('.gs-accordion-header');
            if (!header) return;
            header.addEventListener('click', () => {
                const expanded = acc.getAttribute('aria-expanded') === 'true';
                acc.setAttribute('aria-expanded', String(!expanded));
            });
        });

        // TOC click -> scroll to section and open accordion
        tocLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const targetId = link.getAttribute('data-section');
                const target = document.getElementById(targetId);
                if (!target) return;
                // Open accordion if closed
                if (target.getAttribute('aria-expanded') === 'false') {
                    target.setAttribute('aria-expanded', 'true');
                }
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            });
        });

        // Update active TOC link on scroll
        const contentArea = document.querySelector('#page-getting-started .content-pages') || document.querySelector('.content-pages');
        function updateActiveToc() {
            let activeId = '';
            accordions.forEach(acc => {
                if (acc.classList.contains('hidden')) return;
                const rect = acc.getBoundingClientRect();
                if (rect.top <= 120) {
                    activeId = acc.id;
                }
            });
            tocLinks.forEach(link => {
                link.classList.toggle('active', link.getAttribute('data-section') === activeId);
            });
        }
        if (contentArea) {
            contentArea.addEventListener('scroll', updateActiveToc);
        }
        window.addEventListener('scroll', updateActiveToc);

        // Search
        function doSearch() {
            const query = searchInput.value.trim().toLowerCase();
            searchClear.style.display = query ? 'block' : 'none';

            if (!query) {
                accordions.forEach(acc => {
                    acc.classList.remove('hidden');
                    acc.querySelectorAll('.gs-control').forEach(c => c.classList.remove('hidden'));
                });
                searchResults.textContent = '';
                return;
            }

            let totalMatches = 0;

            accordions.forEach(acc => {
                const sectionKeywords = (acc.getAttribute('data-keywords') || '').toLowerCase();
                const title = (acc.querySelector('.gs-accordion-title')?.textContent || '').toLowerCase();
                const controls = acc.querySelectorAll('.gs-control');
                let sectionMatch = false;

                // Check section-level match
                if (sectionKeywords.includes(query) || title.includes(query)) {
                    sectionMatch = true;
                }

                // Check individual controls
                let controlMatches = 0;
                controls.forEach(ctrl => {
                    const ctrlKeywords = (ctrl.getAttribute('data-keywords') || '').toLowerCase();
                    const ctrlTitle = (ctrl.querySelector('h4')?.textContent || '').toLowerCase();
                    const ctrlText = ctrl.textContent.toLowerCase();
                    if (ctrlKeywords.includes(query) || ctrlTitle.includes(query) || ctrlText.includes(query)) {
                        ctrl.classList.remove('hidden');
                        controlMatches++;
                        sectionMatch = true;
                    } else {
                        ctrl.classList.add('hidden');
                    }
                });

                if (sectionMatch) {
                    acc.classList.remove('hidden');
                    acc.setAttribute('aria-expanded', 'true');
                    totalMatches += controlMatches || 1;
                } else {
                    acc.classList.add('hidden');
                }
            });

            searchResults.textContent = totalMatches > 0
                ? `${totalMatches} result${totalMatches !== 1 ? 's' : ''} found`
                : 'No results found';
        }

        searchInput.addEventListener('input', doSearch);
        searchClear.addEventListener('click', () => {
            searchInput.value = '';
            doSearch();
            searchInput.focus();
        });
    }

    // Run on page switch to init getting-started
    const origNavigateTo = navigateTo;
    // Already defined above, so init on DOMContentLoaded
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(initGettingStarted, 100);
    });

    // --- Init ---
    checkAuth();
})();
