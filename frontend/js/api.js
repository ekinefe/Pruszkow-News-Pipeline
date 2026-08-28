const API = {
    async get(url) {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`GET ${url} failed: ${res.status}`);
        return res.json();
    },

    async post(url, data) {
        const res = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `POST ${url} failed: ${res.status}`);
        }
        return res.json();
    },

    async put(url, data) {
        const res = await fetch(url, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        });
        if (!res.ok) throw new Error(`PUT ${url} failed: ${res.status}`);
        return res.json();
    },

    async del(url) {
        const res = await fetch(url, { method: "DELETE" });
        if (!res.ok) throw new Error(`DELETE ${url} failed: ${res.status}`);
        return res.json();
    },

    getStatus: () => API.get("/api/status"),
    getSettings: () => API.get("/api/settings"),
    getAuthStatus: () => API.get("/api/auth/status"),
    startAuth: () => API.post("/api/auth/start", {}),
    getEmails: () => API.get("/api/emails"),
    getEmail: (id) => API.get(`/api/emails/${id}`),
    fetchEmails: (opts) => API.post("/api/emails/fetch", opts),
    createDrafts: (articles) => API.post("/api/emails/create-drafts", { articles }),
    getArticles: () => API.get("/api/articles"),
    getArticle: (id) => API.get(`/api/articles/${id}`),
    updateArticle: (id, data) => API.put(`/api/articles/${id}`, data),
    deleteArticle: (id) => API.del(`/api/articles/${id}`),
    downloadArticleUrl: (id) => `/api/articles/${id}/download`,
    getIgnoredSenders: () => API.get("/api/settings/ignored"),
    addIgnoredSender: (sender) => API.post("/api/settings/ignored", { sender }),
    removeIgnoredSender: (sender) => API.del(`/api/settings/ignored/${encodeURIComponent(sender)}`),

    getCredentialsStatus: () => API.get("/api/settings/credentials"),
    uploadCredentials: async (file) => {
        const formData = new FormData();
        formData.append("file", file);
        const res = await fetch("/api/settings/credentials", {
            method: "POST",
            body: formData,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Upload failed: ${res.status}`);
        }
        return res.json();
    },

    setAIProvider: (provider) => API.post("/api/settings/ai-provider", { provider }),
    setAPIKey: (key, provider) => API.post(`/api/settings/api-key?provider=${encodeURIComponent(provider)}`, { key }),
    getAPIKeyStatus: (provider) => API.get(`/api/settings/api-key?provider=${encodeURIComponent(provider)}`),
    testAPIKey: (provider) => API.post(`/api/settings/test-key?provider=${encodeURIComponent(provider)}`),
    getSystemRules: () => API.get("/api/settings/system-rules"),
    setSystemRules: (rules) => API.post("/api/settings/system-rules", { rules }),

    getArticleSettings: () => API.get("/api/settings/article-settings"),
    setArticleSettings: (data) => API.post("/api/settings/article-settings", data),

    getUsage: (provider, since, limit) => {
        const params = new URLSearchParams();
        if (provider) params.set("provider", provider);
        if (since) params.set("since", since);
        if (limit) params.set("limit", limit);
        return API.get(`/api/usage?${params}`);
    },
    getUsageSummary: (provider) => API.get(`/api/usage/summary?provider=${encodeURIComponent(provider || "")}`),
    getQuota: () => API.get("/api/usage/quota"),
    setQuota: (quota) => API.post("/api/usage/quota", quota),
    resetUsage: () => API.post("/api/usage/reset", {}),

    generateStream(emailIds, mode, onEvent) {
        const ctrl = new AbortController();
        fetch("/api/emails/generate-stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email_ids: emailIds, mode: mode }),
            signal: ctrl.signal,
        }).then(async (res) => {
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop();
                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        try {
                            onEvent(JSON.parse(line.slice(6)));
                        } catch {}
                    }
                }
            }
        }).catch((err) => {
            if (err.name !== "AbortError") {
                onEvent({ type: "stream_error", message: err.message });
            }
        });
        return ctrl;
    },
};
