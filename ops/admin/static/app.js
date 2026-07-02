let adminToken = "";
let selectedBundle = null;

const $ = (selector) => document.querySelector(selector);

const state = {
  statusPill: $("#status-pill"),
  metrics: $("#metrics"),
  checks: $("#checks"),
  profiles: $("#profiles"),
  detail: $("#profile-detail"),
  backups: $("#backups"),
  restoreJobs: $("#restore-jobs"),
  alertMetrics: $("#alert-metrics"),
  alerts: $("#alerts"),
  access: $("#access"),
  toast: $("#toast"),
};

function clear(node) {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

function append(parent, ...children) {
  children.flat().forEach((child) => {
    if (child === null || child === undefined) return;
    parent.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  });
  return parent;
}

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([key, value]) => {
    if (value === null || value === undefined) return;
    if (key === "className") {
      node.className = value;
    } else if (key === "dataset") {
      Object.entries(value).forEach(([dataKey, dataValue]) => {
        node.dataset[dataKey] = String(dataValue);
      });
    } else if (key === "text") {
      node.textContent = String(value);
    } else {
      node.setAttribute(key, String(value));
    }
  });
  return append(node, children);
}

function toast(message) {
  state.toast.textContent = message;
  state.toast.classList.add("show");
  window.setTimeout(() => state.toast.classList.remove("show"), 2400);
}

async function api(path, options = {}) {
  if (!adminToken) {
    throw new Error("Введите admin token");
  }
  const response = await fetch(`/api/v0${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${adminToken}`,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      message = body.error || message;
    } catch (_error) {
      // Keep the HTTP message.
    }
    throw new Error(message);
  }
  const contentType = response.headers.get("Content-Type") || "";
  if (contentType.includes("application/octet-stream")) {
    return response.blob();
  }
  return response.json();
}

function setStatus(status) {
  const labels = {
    ok: "работает",
    degraded: "частично",
    error: "ошибка",
    offline: "нет связи",
  };
  state.statusPill.textContent = labels[status] || "неизвестно";
  state.statusPill.className = `status-pill ${status || ""}`;
}

function formatBytes(value) {
  if (!Number.isFinite(value)) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let size = value;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function formatDate(seconds) {
  if (!seconds) return "неизвестно";
  return new Date(seconds * 1000).toLocaleString();
}

function renderOverview(overview) {
  setStatus(overview.status);
  clear(state.metrics);
  [
    ["Хост", overview.publicHost || "не определён"],
    ["Профили", overview.profilesCount ?? 0],
    ["Входящий", `${overview.inbound?.protocol || "-"}:${overview.inbound?.port || "-"}`],
  ].forEach(([key, value]) => {
    append(state.metrics, el("div", {}, [el("dt", { text: key }), el("dd", { text: value })]));
  });
}

function renderHealth(health) {
  clear(state.checks);
  Object.entries(health.checks || {}).forEach(([name, item]) => {
    const ok = Boolean(item.ok);
    append(
      state.checks,
      el("div", { className: `check ${ok ? "ok" : "fail"}` }, [
        el("span", { text: name }),
        el("span", { text: ok ? "норма" : item.error || "ошибка" }),
      ]),
    );
  });
}

function profileActionButton(email, action, label) {
  return el("button", {
    type: "button",
    text: label,
    dataset: { action, email },
  });
}

function renderProfiles(payload) {
  clear(state.profiles);
  (payload.profiles || []).forEach((profile) => {
    const email = String(profile.email);
    const enabled = Boolean(profile.enabled);
    append(
      state.profiles,
        el("tr", {}, [
          el("td", { text: email }),
          el("td", { text: enabled ? "включён" : "отключён" }),
          el("td", { text: profile.flow || "-" }),
        el("td", {}, [
          profileActionButton(email, "view", "Открыть"),
          document.createTextNode(" "),
          profileActionButton(email, enabled ? "disable" : "enable", enabled ? "Отключить" : "Включить"),
        ]),
      ]),
    );
  });
}

function manualText(manual) {
  return Object.entries(manual || {})
    .filter(([, value]) => value !== "" && value !== null && value !== undefined)
    .map(([key, value]) => `${key}: ${value}`)
    .join("\n");
}

function renderProfileBundle(bundle) {
  selectedBundle = bundle;
  const directLinks = bundle.hiddify?.directLinks || [];
  const manual = bundle.v2raytun?.manual || {};
  const warnings = bundle.diagnostics?.warnings || [];
  state.detail.classList.remove("empty");
  clear(state.detail);

  const left = el("div", {}, [el("pre", { className: "link-box", text: directLinks.join("\n\n") || "ссылки недоступны" })]);
  if (warnings.length) {
    append(left, el("p", { className: "muted", text: warnings.join(" ") }));
  }

  const fields = el("dl", { className: "fields" });
  Object.entries(manual).forEach(([key, value]) => {
    append(fields, el("dt", { text: key }), el("dd", { text: value || "-" }));
  });

  append(state.detail, left, fields);
}

function renderBackups(payload) {
  clear(state.backups);
  const backups = payload.backups || [];
  const policy = payload.policy || {};
  append(
    state.backups,
    el("p", {
      className: "muted",
      text: `Хранение: ${policy.retentionDays || "-"} дней, минимум ${policy.keepMin || "-"} шт. · Всего ${formatBytes(payload.totalSize || 0)}`,
    }),
  );
  if (!backups.length) {
    append(state.backups, el("p", { className: "muted", text: "Бэкапов нет" }));
    return;
  }
  backups.forEach((backup) => {
    const info = el("div", {}, [
      el("strong", { text: backup.name }),
      el("div", { className: "muted", text: `${formatBytes(backup.size)} · ${formatDate(backup.mtime)}` }),
    ]);
    const button = el("button", {
      type: "button",
      text: "Скачать",
      dataset: { backup: backup.name, backupAction: "download" },
    });
    const removeButton = el("button", {
      className: "danger",
      type: "button",
      text: "Удалить",
      dataset: { backup: backup.name, backupAction: "delete" },
    });
    const restoreButton = el("button", {
      className: "danger",
      type: "button",
      text: "Восстановить",
      dataset: { backup: backup.name, backupAction: "restore" },
    });
    const actions = el("div", { className: "actions" }, [button, restoreButton, removeButton]);
    append(state.backups, el("div", { className: "backup-item" }, [info, actions]));
  });
}

function renderRestoreJobs(payload) {
  clear(state.restoreJobs);
  const jobs = payload.jobs || [];
  append(state.restoreJobs, el("h3", { text: "Восстановление" }));
  if (!jobs.length) {
    append(state.restoreJobs, el("p", { className: "muted", text: "Заявок нет" }));
    return;
  }
  jobs.slice(0, 5).forEach((job) => {
    const meta = [
      job.backupName || "-",
      job.updatedAt ? formatDate(job.updatedAt) : "нет времени",
      job.error || "",
    ].filter(Boolean);
    append(
      state.restoreJobs,
      el("div", { className: `restore-job ${job.status || "queued"}` }, [
        el("strong", { text: job.status || "queued" }),
        el("span", { text: meta.join(" · ") }),
      ]),
    );
  });
}

function renderAlerts(payload) {
  clear(state.alertMetrics);
  [
    ["Статус", payload.enabled ? "включены" : "выключены"],
    ["Telegram", payload.configured ? "настроен" : "не настроен"],
    ["Последнее", payload.state?.updatedAt ? formatDate(payload.state.updatedAt) : "нет данных"],
  ].forEach(([key, value]) => {
    append(state.alertMetrics, el("div", {}, [el("dt", { text: key }), el("dd", { text: value })]));
  });

  clear(state.alerts);
  Object.entries(payload.health?.checks || {}).forEach(([name, item]) => {
    const ok = Boolean(item.ok);
    append(
      state.alerts,
      el("div", { className: `check ${ok ? "ok" : "fail"}` }, [
        el("span", { text: name }),
        el("span", { text: ok ? "норма" : item.error || "ошибка" }),
      ]),
    );
  });
}

async function refreshAll() {
  const tasks = [
    ["Обзор", api("/overview"), renderOverview],
    ["Состояние", api("/health"), renderHealth],
    ["Профили", api("/profiles"), renderProfiles],
    ["Бэкапы", api("/backups"), renderBackups],
    ["Восстановление", api("/restore-requests"), renderRestoreJobs],
    ["Alerts", api("/alerts"), renderAlerts],
  ];
  const results = await Promise.all(
    tasks.map(async ([label, promise, render]) => {
      try {
        render(await promise);
        return true;
      } catch (error) {
        toast(`${label}: ${error.message}`);
        return false;
      }
    }),
  );
  if (!results.some(Boolean)) {
    throw new Error("Не удалось загрузить данные");
  }
}

async function loadProfile(email) {
  const bundle = await api(`/profiles/${encodeURIComponent(email)}`);
  renderProfileBundle(bundle);
}

async function createProfile() {
  const email = $("#profile-name").value.trim();
  const comment = $("#profile-comment").value.trim();
  const bundle = await api("/profiles", {
    method: "POST",
    body: JSON.stringify({ email, comment }),
  });
  $("#profile-name").value = "";
  $("#profile-comment").value = "";
  await refreshAll();
  renderProfileBundle(bundle);
  toast("Профиль создан");
}

async function setProfile(email, action) {
  await api(`/profiles/${encodeURIComponent(email)}/${action}`, { method: "POST" });
  await refreshAll();
  toast(action === "enable" ? "Профиль включён" : "Профиль отключён");
}

async function loadAccess() {
  const payload = await api("/access");
  state.access.textContent = [
    "Mirage Admin",
    `URL: ${payload.admin.localUrl}`,
    `SSH: ${payload.admin.sshTunnelCommand}`,
    "",
    "3x-ui",
    `URL: ${payload.panel.localUrl}`,
    `SSH: ${payload.panel.sshTunnelCommand}`,
  ].join("\n");
  return payload;
}

async function createBackup() {
  const backup = await api("/backups", { method: "POST" });
  await refreshAll();
  toast(`Бэкап создан: ${backup.name}`);
}

async function importBackup(file) {
  if (!file) return;
  if (!window.confirm(`Импортировать backup ${file.name}?`)) return;
  const backup = await api("/backups/import", {
    method: "POST",
    body: await file.arrayBuffer(),
    headers: { "Content-Type": "application/octet-stream" },
  });
  await refreshAll();
  toast(`Бэкап импортирован: ${backup.name}`);
}

async function downloadBackup(name) {
  const blob = await api(`/backups/${encodeURIComponent(name)}`, {
    headers: { "Content-Type": "application/octet-stream" },
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function deleteBackup(name) {
  if (!window.confirm(`Удалить backup ${name}?`)) return;
  const encodedName = encodeURIComponent(name);
  await api(`/backups/${encodedName}?confirmName=${encodedName}`, { method: "DELETE" });
  await refreshAll();
  toast("Бэкап удалён");
}

async function queueRestore(name) {
  const typed = window.prompt(`Для восстановления введи имя backup:\n${name}`);
  if (typed !== name) {
    toast("Восстановление отменено");
    return;
  }
  const confirmed = window.confirm("Восстановление перезапустит 3x-ui и временно прервёт VPN. Продолжить?");
  if (!confirmed) return;
  const job = await api(`/backups/${encodeURIComponent(name)}/restore`, {
    method: "POST",
    body: JSON.stringify({ confirm: "restore", confirmName: name, ackDowntime: true }),
  });
  await refreshAll();
  toast(`Restore job создан: ${job.jobId}`);
}

async function pruneBackups() {
  const preview = await api("/backups/prune", { method: "POST", body: JSON.stringify({ dryRun: true }) });
  if (!preview.pruned.length) {
    toast("Старых бэкапов для удаления нет");
    return;
  }
  const size = formatBytes(preview.pruned.reduce((total, backup) => total + backup.size, 0));
  const confirmed = window.confirm(`Удалить старые backup-файлы: ${preview.pruned.length} шт., ${size}?`);
  if (!confirmed) return;
  const result = await api("/backups/prune", {
    method: "POST",
    body: JSON.stringify({ dryRun: false, confirm: "prune" }),
  });
  await refreshAll();
  toast(`Удалено старых бэкапов: ${result.pruned.length}`);
}

async function testAlert() {
  await api("/alerts/test", { method: "POST" });
  await refreshAll();
  toast("Тестовое уведомление отправлено");
}

async function copyText(value) {
  if (!value) return;
  await navigator.clipboard.writeText(value);
  toast("Скопировано");
}

function bindEvents() {
  $("#profile-form").addEventListener("submit", (event) => {
    event.preventDefault();
    createProfile().catch((error) => toast(error.message));
  });

  $("#connect").addEventListener("click", async () => {
    adminToken = $("#token").value.trim();
    try {
      await refreshAll();
      toast("Подключено");
    } catch (error) {
      setStatus("error");
      toast(error.message);
    }
  });

  $("#refresh").addEventListener("click", () => refreshAll().catch((error) => toast(error.message)));
  $("#create-profile").addEventListener("click", () => createProfile().catch((error) => toast(error.message)));
  $("#create-backup").addEventListener("click", () => createBackup().catch((error) => toast(error.message)));
  $("#import-backup").addEventListener("click", () => $("#backup-file").click());
  $("#backup-file").addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    importBackup(file)
      .catch((error) => toast(error.message))
      .finally(() => {
        event.target.value = "";
      });
  });
  $("#prune-backups").addEventListener("click", () => pruneBackups().catch((error) => toast(error.message)));
  $("#test-alert").addEventListener("click", () => testAlert().catch((error) => toast(error.message)));
  $("#load-access").addEventListener("click", () => loadAccess().catch((error) => toast(error.message)));
  $("#open-panel").addEventListener("click", async () => {
    try {
      const payload = await loadAccess();
      window.open(payload.panel.localUrl, "_blank", "noopener");
    } catch (error) {
      toast(error.message);
    }
  });

  $("#profiles").addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    const email = button.dataset.email;
    const action = button.dataset.action;
    if (action === "view") {
      loadProfile(email).catch((error) => toast(error.message));
    } else {
      setProfile(email, action).catch((error) => toast(error.message));
    }
  });

  $("#backups").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-backup]");
    if (!button) return;
    if (button.dataset.backupAction === "delete") {
      deleteBackup(button.dataset.backup).catch((error) => toast(error.message));
      return;
    }
    if (button.dataset.backupAction === "restore") {
      queueRestore(button.dataset.backup).catch((error) => toast(error.message));
      return;
    }
    downloadBackup(button.dataset.backup).catch((error) => toast(error.message));
  });

  $("#copy-link").addEventListener("click", () => {
    const link = selectedBundle?.hiddify?.directLinks?.[0] || "";
    copyText(link).catch((error) => toast(error.message));
  });

  $("#copy-fields").addEventListener("click", () => {
    copyText(manualText(selectedBundle?.v2raytun?.manual)).catch((error) => toast(error.message));
  });
}

bindEvents();
