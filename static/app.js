const $ = (id) => document.getElementById(id);

const state = {
  mode: "timer",
  clients: [],
  projects: [],
  tasks: [],
  running: null,
  tickHandle: null,
  recentOffset: 0,
  recentPageSize: 10,
};

// Session-lifetime cache for the cascade dropdowns. Reads dominate this
// app's traffic; without caching every keystroke committed to a combobox
// re-hits ES. Invalidated whenever we submit an entry that could add a
// new client/project/task.
const cache = {
  clients: null,
  projects: new Map(),  // key: clientId or "__all__"
  tasks: new Map(),     // key: projectId or "__all__"
};

function invalidateLookupCache() {
  cache.clients = null;
  cache.projects.clear();
  cache.tasks.clear();
}

function csrfToken() {
  return document.querySelector('meta[name="csrf-token"]')?.content || "";
}

async function api(path, opts = {}) {
  const method = (opts.method || "GET").toUpperCase();
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const t = csrfToken();
    if (t) headers["X-CSRF-Token"] = t;
  }
  const r = await fetch(path, { ...opts, headers });
  if (r.status === 401) {
    // Session expired or missing; bounce to login preserving return path.
    const next = encodeURIComponent(window.location.pathname);
    window.location.href = `/login?next=${next}`;
    throw new Error("Redirecting to login");
  }
  if (r.status === 204) return null;
  if (!r.ok) {
    const msg = await r.text().catch(() => r.statusText);
    throw new Error(msg || `HTTP ${r.status}`);
  }
  const ct = r.headers.get("content-type") || "";
  return ct.includes("application/json") ? r.json() : r.text();
}

function fillDatalist(id, items, labelFn) {
  const dl = $(id);
  dl.innerHTML = "";
  const seen = new Set();
  for (const it of items) {
    const label = labelFn(it);
    if (!label || seen.has(label)) continue;
    seen.add(label);
    const opt = document.createElement("option");
    opt.value = label;
    dl.appendChild(opt);
  }
}

async function loadClients() {
  if (cache.clients === null) {
    cache.clients = await api("/api/clients").catch(() => []);
  }
  state.clients = cache.clients;
  fillDatalist("clients-list", state.clients, (c) => c.clientName);
}

async function loadProjects() {
  const clientName = $("client-input").value.trim();
  const client = state.clients.find((c) => c.clientName === clientName);
  if (clientName && !client) {
    state.projects = [];
  } else {
    const key = client ? client.clientId : "__all__";
    if (!cache.projects.has(key)) {
      const qs = client ? `?client=${encodeURIComponent(client.clientId)}` : "";
      cache.projects.set(key, await api(`/api/projects${qs}`).catch(() => []));
    }
    state.projects = cache.projects.get(key);
  }
  fillDatalist("projects-list", state.projects, (p) => p.name);
}

async function loadTasks() {
  const projectName = $("project-input").value.trim();
  const project = state.projects.find((p) => p.name === projectName);
  if (projectName && !project) {
    state.tasks = [];
  } else {
    const key = project ? project.projectId : "__all__";
    if (!cache.tasks.has(key)) {
      const qs = project ? `?project=${encodeURIComponent(project.projectId)}` : "";
      cache.tasks.set(key, await api(`/api/tasks${qs}`).catch(() => []));
    }
    state.tasks = cache.tasks.get(key);
  }
  fillDatalist("tasks-list", state.tasks, (t) => t.name);
}

function currentProjectPayload() {
  const clientName = $("client-input").value.trim();
  const projectName = $("project-input").value.trim();
  if (!projectName && !clientName) return { project: null, projectId: null };

  const existing = state.projects.find(
    (p) => p.name === projectName && p.clientName === clientName
  );
  if (existing) {
    return {
      project: { name: existing.name, clientId: existing.clientId, clientName: existing.clientName },
      projectId: existing.projectId,
    };
  }
  const client = state.clients.find((c) => c.clientName === clientName);
  return {
    project: { name: projectName, clientId: client ? client.clientId : "", clientName },
    projectId: "",
  };
}

function currentTaskPayload() {
  const name = $("task-input").value.trim();
  return name ? { name } : null;
}

function formPayload() {
  const { project, projectId } = currentProjectPayload();
  return {
    description: $("description-input").value.trim() || null,
    project,
    projectId,
    task: currentTaskPayload(),
  };
}

function fmtElapsed(ms) {
  const s = Math.max(0, Math.floor(ms / 1000));
  const pad = (n) => n.toString().padStart(2, "0");
  return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`;
}

function startTicker() {
  if (state.tickHandle) clearInterval(state.tickHandle);
  const started = new Date(state.running.start).getTime();
  const tick = () => { $("elapsed").textContent = fmtElapsed(Date.now() - started); };
  tick();
  state.tickHandle = setInterval(tick, 1000);
}

function stopTicker() {
  if (state.tickHandle) { clearInterval(state.tickHandle); state.tickHandle = null; }
}

function summariseEntry(e) {
  // Plain-text version used for the running-timer summary and hover titles.
  const desc = e.description || "(no description)";
  const meta = [e.project?.clientName, e.project?.name, e.task?.name].filter(Boolean);
  return meta.length ? `${desc} — ${meta.join(" · ")}` : desc;
}

function fmtDuration(ms) {
  const s = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h && m) return `${h}h ${m}m`;
  if (h) return `${h}h`;
  if (m) return `${m}m`;
  return `${s}s`;
}

function formatEntryInfo(e) {
  const start = e.timeInterval?.start;
  if (!start) return "";
  const startDate = new Date(start);
  if (isNaN(startDate)) return "";
  const dateStr = startDate.toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
  const end = e.timeInterval?.end;
  if (!end) return dateStr;
  const endDate = new Date(end);
  if (isNaN(endDate)) return dateStr;
  return `${dateStr} · ${fmtDuration(endDate - startDate)}`;
}

function renderEntryInto(node, e) {
  // DOM version used for recent-entry list items so we can bold the
  // description and add a smaller meta subline without hand-rolling escapes.
  node.textContent = "";

  const main = document.createElement("div");
  const strong = document.createElement("strong");
  strong.textContent = e.description || "(no description)";
  main.appendChild(strong);
  const meta = [e.project?.clientName, e.project?.name, e.task?.name].filter(Boolean);
  if (meta.length) {
    main.appendChild(document.createTextNode(` — ${meta.join(" · ")}`));
  }
  node.appendChild(main);

  const info = formatEntryInfo(e);
  if (info) {
    const sub = document.createElement("div");
    sub.className = "entry-meta";
    sub.textContent = info;
    node.appendChild(sub);
  }
}

function renderRunning() {
  const running = state.running;
  if (!running) {
    $("running").hidden = true;
    $("form-panel").hidden = false;
    stopTicker();
    return;
  }
  $("form-panel").hidden = true;
  $("running").hidden = false;
  $("running-summary").textContent = summariseEntry(running);
  const started = new Date(running.start);
  $("started-at").textContent = isNaN(started) ? running.start : started.toLocaleString();
  startTicker();
}

const pad2 = (n) => n.toString().padStart(2, "0");

function toLocalIsoInput(d) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}

function toIsoWithOffset(localValue) {
  if (!localValue) return null;
  const d = new Date(localValue);
  if (isNaN(d)) return null;
  const off = -d.getTimezoneOffset();
  const sign = off >= 0 ? "+" : "-";
  const oh = pad2(Math.floor(Math.abs(off) / 60));
  const om = pad2(Math.abs(off) % 60);
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}${sign}${oh}${om}`;
}

function applyMode() {
  const manual = state.mode === "manual";
  document.querySelectorAll(".manual-only").forEach((el) => { el.hidden = !manual; });
  $("submit-btn").textContent = manual ? "Save entry" : "Start timer";
  document.querySelectorAll(".mode-option").forEach((btn) => {
    const active = btn.dataset.mode === state.mode;
    btn.classList.toggle("is-active", active);
    btn.setAttribute("aria-selected", active ? "true" : "false");
  });

  if (manual) {
    const now = new Date();
    if (!$("start-input").value) $("start-input").value = toLocalIsoInput(new Date(now - 30 * 60000));
    if (!$("end-input").value) $("end-input").value = toLocalIsoInput(now);
  } else {
    $("start-input").value = "";
    $("end-input").value = "";
  }
}

function prependRecent(entry) {
  const ul = $("recent-list");
  const li = document.createElement("li");
  renderEntryInto(li, entry);
  li.title = "Click to fill the form from this entry";
  li.addEventListener("click", () => fillFromEntry(entry));
  ul.insertBefore(li, ul.firstChild);
  state.recentOffset += 1;
}

async function submitForm(e) {
  e.preventDefault();
  const err = $("form-error");
  err.hidden = true;
  const base = formPayload();

  try {
    if (state.mode === "timer") {
      const startIso = toIsoWithOffset($("start-input").value);
      const body = startIso ? { ...base, start: startIso } : base;
      const r = await api("/api/timers", { method: "POST", body: JSON.stringify(body) });
      if (r.stopped?.timeInterval) {
        prependRecent(r.stopped);
        invalidateLookupCache();
      }
      state.running = r.started;
      renderRunning();
    } else {
      const body = {
        ...base,
        start: toIsoWithOffset($("start-input").value),
        end: toIsoWithOffset($("end-input").value),
      };
      const r = await api("/api/entries", { method: "POST", body: JSON.stringify(body) });
      prependRecent({
        id: r.id,
        description: base.description,
        project: base.project,
        task: base.task,
        timeInterval: { start: body.start, end: body.end },
      });
      invalidateLookupCache();
      $("description-input").value = "";
    }
  } catch (ex) {
    err.textContent = ex.message;
    err.hidden = false;
  }
}

async function stopRunning() {
  if (!state.running) return;
  try {
    const r = await api(`/api/timers/${state.running.id}/stop`, { method: "POST" });
    // 201 returns the entry directly; 202 wraps it as { id, status, entry }.
    const entry = r?.entry || r;
    if (entry?.timeInterval) {
      prependRecent(entry);
      invalidateLookupCache();
    }
  } catch {}
  state.running = null;
  renderRunning();
}

async function cancelRunning() {
  if (!state.running) return;
  await api(`/api/timers/${state.running.id}`, { method: "DELETE" }).catch(() => {});
  state.running = null;
  renderRunning();
}

async function loadRecent(reset = false) {
  if (reset) {
    state.recentOffset = 0;
    $("recent-list").innerHTML = "";
  }
  const entries = await api(
    `/api/entries/recent?limit=${state.recentPageSize}&offset=${state.recentOffset}`
  ).catch(() => []);
  const ul = $("recent-list");
  for (const e of entries) {
    const li = document.createElement("li");
    renderEntryInto(li, e);
    li.title = "Click to fill the form from this entry";
    li.addEventListener("click", () => fillFromEntry(e));
    ul.appendChild(li);
  }
  state.recentOffset += entries.length;
  $("load-more").hidden = entries.length < state.recentPageSize;
}

async function fillFromEntry(e) {
  $("client-input").value = e.project?.clientName || "";
  $("project-input").value = e.project?.name || "";
  $("task-input").value = e.task?.name || "";
  $("description-input").value = e.description || "";
  await loadProjects();
  await loadTasks();
}

async function refreshRunning() {
  try { state.running = await api("/api/timers"); }
  catch { state.running = null; }
  renderRunning();
}

async function onClientChange() {
  const clientName = $("client-input").value.trim();
  await loadProjects();
  // If the currently-typed project doesn't belong to the new client, drop it
  // and its downstream task so we can't submit a nonsense pairing.
  const projectName = $("project-input").value.trim();
  const stillValid = projectName && state.projects.some(
    (p) => p.name === projectName && p.clientName === clientName
  );
  if (projectName && !stillValid) {
    $("project-input").value = "";
    $("task-input").value = "";
  }
  await loadTasks();
}

async function onProjectChange() {
  const projectName = $("project-input").value.trim();
  const taskName = $("task-input").value.trim();
  // Clear task if we've moved to a different project. It might be legitimate
  // (same task name reused across projects) but that's a re-type, not silent
  // carry-over of nonsense.
  if (taskName) $("task-input").value = "";
  await loadTasks();
}

function wireEvents() {
  document.querySelectorAll(".mode-option").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.mode = btn.dataset.mode;
      applyMode();
    });
  });
  $("client-input").addEventListener("change", onClientChange);
  $("project-input").addEventListener("change", onProjectChange);
  $("entry-form").addEventListener("submit", submitForm);
  $("stop-btn").addEventListener("click", stopRunning);
  $("cancel-btn").addEventListener("click", cancelRunning);
  $("load-more").addEventListener("click", () => loadRecent(false));
}

async function init() {
  wireEvents();
  applyMode();
  await Promise.all([loadClients(), loadProjects(), loadTasks(), refreshRunning(), loadRecent(true)]);
}

init();
