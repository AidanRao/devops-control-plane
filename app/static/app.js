(function () {
  "use strict";

  const API_BASE = ""; // 与 FastAPI 部署在同一域名下
  let statusChart = null;

  document.addEventListener("DOMContentLoaded", function () {
    initTheme();
    initThemeToggle();
    initAgentsSection();
    initCommandSection();
    initTaskSection();
    updateSummaryCards();
  });

  // ---------- 主题切换 ----------
  function initTheme() {
    const saved = window.localStorage.getItem("devops-theme");
    const prefersDark = window.matchMedia(
      "(prefers-color-scheme: dark)"
    ).matches;
    const theme = saved || (prefersDark ? "dark" : "light");
    applyTheme(theme);
  }

  function initThemeToggle() {
    const btn = document.getElementById("themeToggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      const isDark = document.documentElement.classList.contains("dark");
      applyTheme(isDark ? "light" : "dark");
    });
  }

  function applyTheme(theme) {
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
    window.localStorage.setItem("devops-theme", theme);
    const icon = document.getElementById("themeIcon");
    const themeLabel = document.getElementById("themeLabel");
    if (icon) {
      icon.textContent = theme === "dark" ? "light_mode" : "dark_mode";
    }
    if (themeLabel) {
      themeLabel.textContent = theme === "dark" ? "浅色模式" : "深色模式";
    }
  }

  function updateSummaryCards(payload) {
    const data = payload || {};
    const onlineCount = document.getElementById("summaryOnlineCount");
    const taskState = document.getElementById("summaryTaskState");
    const taskHint = document.getElementById("summaryTaskHint");
    const focus = document.getElementById("summaryFocus");

    if (onlineCount && typeof data.onlineCount !== "undefined") {
      onlineCount.textContent = String(data.onlineCount);
    }
    if (taskState && data.taskState) {
      taskState.textContent = data.taskState;
    }
    if (taskHint && data.taskHint) {
      taskHint.textContent = data.taskHint;
    }
    if (focus && data.focus) {
      focus.textContent = data.focus;
    }
  }

  function updateLastTaskSummary(taskState, taskHint) {
    updateSummaryCards({
      taskState: taskState,
      taskHint: taskHint,
    });
  }

  // ---------- 在线 Agent 列表 ----------
  function initAgentsSection() {
    fetchAgents();
    const refreshBtn = document.getElementById("refreshAgentsBtn");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", fetchAgents);
    }
    // 定时刷新
    window.setInterval(fetchAgents, 15000);
  }

  async function fetchAgents() {
    try {
      const res = await fetch(`${API_BASE}/api/agents`);
      if (!res.ok) throw new Error(`请求失败: ${res.status}`);
      const data = await res.json();
      renderAgents(Array.isArray(data.agents) ? data.agents : []);
    } catch (err) {
      console.error("获取在线 Agent 列表失败", err);
    }
  }

  function renderAgents(agents) {
    const tbody = document.getElementById("agentsTableBody");
    const empty = document.getElementById("agentsEmptyState");
    const countEl = document.getElementById("agentsCount");
    if (!tbody || !empty || !countEl) return;

    tbody.innerHTML = "";

    if (!agents.length) {
      empty.classList.remove("hidden");
      countEl.textContent = "0";
      updateSummaryCards({ onlineCount: 0 });
      return;
    }

    empty.classList.add("hidden");
    countEl.textContent = String(agents.length);
    updateSummaryCards({ onlineCount: agents.length });

    agents.forEach(function (agent) {
      const tr = document.createElement("tr");
      tr.className =
        "bg-white/60 odd:bg-white/80 dark:bg-slate-900/40 odd:dark:bg-slate-900/60";

      const idCell = document.createElement("td");
      idCell.className = "px-4 py-2 text-xs font-mono text-slate-800 dark:text-slate-100";
      idCell.textContent = agent.device_id || "-";
      tr.appendChild(idCell);

      const tokenCell = document.createElement("td");
      tokenCell.className = "px-4 py-2 text-xs";
      const badge = document.createElement("span");
      badge.className =
        "badge bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200";
      const dot = document.createElement("span");
      dot.className = "badge-dot bg-emerald-500";
      const label = document.createElement("span");
      if (agent.hasDeviceToken) {
        label.textContent = "有 deviceToken";
      } else {
        badge.className =
          "badge bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300";
        dot.className = "badge-dot bg-slate-400";
        label.textContent = "无";
      }
      badge.appendChild(dot);
      badge.appendChild(label);
      tokenCell.appendChild(badge);
      tr.appendChild(tokenCell);

      const hbCell = document.createElement("td");
      hbCell.className = "px-4 py-2 text-xs text-slate-600 dark:text-slate-300";
      hbCell.textContent = formatTime(agent.lastHeartbeat);
      tr.appendChild(hbCell);

      tbody.appendChild(tr);
    });
  }

  function formatTime(value) {
    if (!value) return "—";
    const d = new Date(value);
    if (isNaN(d.getTime())) {
      return String(value);
    }
    return d.toLocaleString();
  }

  // ---------- 命令下发 ----------
  function initCommandSection() {
    const form = document.getElementById("commandForm");
    if (!form) return;
    form.addEventListener("submit", handleCommandSubmit);
  }

  async function handleCommandSubmit(event) {
    event.preventDefault();
    const input = document.getElementById("commandInput");
    const timeoutInput = document.getElementById("timeoutInput");
    const statusEl = document.getElementById("commandStatus");
    const taskIdInput = document.getElementById("taskIdInput");

    if (!input || !timeoutInput || !statusEl) return;

    const command = input.value.trim();
    const timeoutSeconds = parseInt(timeoutInput.value || "30", 10) || 30;

    if (!command) {
      statusEl.textContent = "请先输入要下发的命令。";
      statusEl.className =
        "text-xs text-rose-500 dark:text-rose-300";
      updateSummaryCards({ focus: "命令下发" });
      return;
    }

    statusEl.textContent = "正在下发命令...";
    statusEl.className = "text-xs text-slate-500 dark:text-slate-400";
    updateSummaryCards({
      focus: "命令下发",
      taskState: "下发中",
      taskHint: "正在创建新的任务编号。",
    });

    try {
      const res = await fetch(`${API_BASE}/api/commands`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          targets: [],
          command: command,
          timeoutSeconds: timeoutSeconds,
        }),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`HTTP ${res.status}: ${text}`);
      }

      const data = await res.json();
      const taskId = data.task_uuid;

      statusEl.textContent = `命令已下发，task_uuid = ${taskId}`;
      statusEl.className =
        "text-xs text-emerald-600 dark:text-emerald-300";
      updateLastTaskSummary("已下发", `任务编号 ${taskId} 已创建。`);

      if (taskIdInput) {
        taskIdInput.value = taskId;
      }
    } catch (err) {
      console.error("下发命令失败", err);
      statusEl.textContent = "下发命令失败，请稍后重试或检查服务端日志。";
      statusEl.className = "text-xs text-rose-500 dark:text-rose-300";
      updateLastTaskSummary("下发失败", "请检查服务端状态后重试。");
    }
  }

  // ---------- 任务查询 & ECharts ----------
  function initTaskSection() {
    const btn = document.getElementById("queryTaskBtn");
    if (!btn) return;
    btn.addEventListener("click", function () {
      const input = document.getElementById("taskIdInput");
      if (!input) return;
      const taskId = input.value.trim();
      if (!taskId) {
        const statusEl = document.getElementById("taskStatusText");
        if (statusEl) {
          statusEl.textContent = "请先填写 task_uuid。";
          statusEl.className =
            "text-xs text-rose-500 dark:text-rose-300";
        }
        updateSummaryCards({ focus: "任务查询" });
        return;
      }
      updateSummaryCards({ focus: "任务查询" });
      fetchTask(taskId);
    });

    if (typeof echarts !== "undefined") {
      const el = document.getElementById("statusChart");
      if (el) {
        statusChart = echarts.init(el);
        statusChart.setOption(baseChartOption([], []));
      }
      window.addEventListener("resize", function () {
        if (statusChart) statusChart.resize();
      });
    }
  }

  async function fetchTask(taskId) {
    const statusEl = document.getElementById("taskStatusText");
    const tbody = document.getElementById("taskResultsBody");
    if (statusEl) {
      statusEl.textContent = "正在查询任务...";
      statusEl.className = "text-xs text-slate-500 dark:text-slate-400";
    }
    updateLastTaskSummary("查询中", `正在查询任务 ${taskId}。`);
    if (tbody) {
      tbody.innerHTML = "";
    }

    try {
      const res = await fetch(`${API_BASE}/api/commands/${encodeURIComponent(taskId)}`);
      if (!res.ok) {
        if (res.status === 404) {
          if (statusEl) {
            statusEl.textContent = "未找到对应 task_uuid 的任务。";
            statusEl.className =
              "text-xs text-rose-500 dark:text-rose-300";
          }
          updateLastTaskSummary("未找到任务", `任务 ${taskId} 不存在。`);
          if (statusChart) {
            statusChart.setOption(baseChartOption([], []));
          }
          return;
        }
        const text = await res.text();
        throw new Error(`HTTP ${res.status}: ${text}`);
      }

      const data = await res.json();
      renderTask(data);
    } catch (err) {
      console.error("查询任务失败", err);
      if (statusEl) {
        statusEl.textContent = "查询失败，请稍后重试。";
        statusEl.className = "text-xs text-rose-500 dark:text-rose-300";
      }
      updateLastTaskSummary("查询失败", "请稍后重试任务查询。");
      if (statusChart) {
        statusChart.setOption(baseChartOption([], []));
      }
    }
  }

  function renderTask(data) {
    const statusEl = document.getElementById("taskStatusText");
    const tbody = document.getElementById("taskResultsBody");
    if (!statusEl || !tbody) return;

    const results = data.results || {};
    const entries = Object.keys(results).map(function (key) {
      return [key, results[key]];
    });

    if (!entries.length) {
      statusEl.textContent = `任务状态：${data.status || "未知"}（尚无结果分片）`;
      statusEl.className = "text-xs text-slate-600 dark:text-slate-300";
      updateLastTaskSummary(
        data.status || "未知",
        "任务已创建，正在等待 Agent 返回结果。"
      );
      if (statusChart) {
        statusChart.setOption(baseChartOption([], []));
      }
      return;
    }

    statusEl.textContent = `任务状态：${data.status}`;
    statusEl.className = "text-xs text-slate-600 dark:text-slate-300";
    updateLastTaskSummary(
      data.status || "未知",
      `已收到 ${entries.length} 台 Agent 的执行结果。`
    );

    tbody.innerHTML = "";

    const statusCounts = {};

    entries.forEach(function ([agentId, item]) {
      const normalized = normalizeAgentStatus(item);
      statusCounts[normalized] = (statusCounts[normalized] || 0) + 1;

      const tr = document.createElement("tr");
      tr.className =
        "bg-white/60 odd:bg-white/80 dark:bg-slate-900/40 odd:dark:bg-slate-900/60";

      const agentCell = document.createElement("td");
      agentCell.className =
        "px-3 py-2 text-[0.7rem] font-mono text-slate-800 dark:text-slate-100";
      agentCell.textContent = item.agent_id || agentId;
      tr.appendChild(agentCell);

      const statusCell = document.createElement("td");
      statusCell.className = "px-3 py-2";
      const badge = document.createElement("span");
      const badgeClasses = getStatusBadgeClass(normalized);
      badge.className = "badge " + badgeClasses;
      const dot = document.createElement("span");
      dot.className = "badge-dot " + getStatusDotClass(normalized);
      const label = document.createElement("span");
      label.textContent = normalized;
      badge.appendChild(dot);
      badge.appendChild(label);
      statusCell.appendChild(badge);
      tr.appendChild(statusCell);

      const exitCell = document.createElement("td");
      exitCell.className = "px-3 py-2 text-[0.7rem] text-slate-600 dark:text-slate-300";
      exitCell.textContent =
        typeof item.exitCode === "number" ? String(item.exitCode) : "-";
      tr.appendChild(exitCell);

      const stdoutCell = document.createElement("td");
      stdoutCell.className =
        "px-3 py-2 text-[0.7rem] text-slate-700 dark:text-slate-200";
      stdoutCell.innerHTML =
        "<pre class='code-block whitespace-pre-wrap break-all max-h-24 overflow-auto'>" +
        escapeHtml(item.stdout || "") +
        "</pre>";
      tr.appendChild(stdoutCell);

      const stderrCell = document.createElement("td");
      stderrCell.className =
        "px-3 py-2 text-[0.7rem] text-rose-700 dark:text-rose-300";
      stderrCell.innerHTML =
        "<pre class='code-block whitespace-pre-wrap break-all max-h-24 overflow-auto'>" +
        escapeHtml(item.stderr || "") +
        "</pre>";
      tr.appendChild(stderrCell);

      tbody.appendChild(tr);
    });

    if (statusChart) {
      const categories = Object.keys(statusCounts);
      const values = categories.map(function (k) {
        return statusCounts[k] || 0;
      });
      statusChart.setOption(baseChartOption(categories, values));
    }
  }

  function normalizeAgentStatus(item) {
    const raw = (item && item.status) || "";
    if (raw === "Running") return "Running";
    if (raw === "Finished") {
      if (typeof item.exitCode === "number" && item.exitCode === 0) {
        return "Succeeded";
      }
      return "Failed";
    }
    return raw || "Unknown";
  }

  function getStatusBadgeClass(status) {
    if (status === "Succeeded") {
      return "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200";
    }
    if (status === "Failed") {
      return "bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-200";
    }
    if (status === "Running") {
      return "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200";
    }
    return "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300";
  }

  function getStatusDotClass(status) {
    if (status === "Succeeded") return "bg-emerald-500";
    if (status === "Failed") return "bg-rose-500";
    if (status === "Running") return "bg-amber-500";
    return "bg-slate-400";
  }

  function baseChartOption(categories, values) {
    return {
      grid: { left: 32, right: 16, top: 30, bottom: 26 },
      tooltip: { trigger: "axis" },
      xAxis: {
        type: "category",
        data: categories,
        axisLine: { lineStyle: { color: "#cbd5f5" } },
        axisLabel: { color: "#64748b", fontSize: 10 },
      },
      yAxis: {
        type: "value",
        minInterval: 1,
        axisLine: { show: false },
        splitLine: { lineStyle: { color: "#e2e8f0" } },
        axisLabel: { color: "#94a3b8", fontSize: 10 },
      },
      series: [
        {
          type: "bar",
          data: values,
          barWidth: 24,
          itemStyle: {
            color: "#2563eb",
            borderRadius: [6, 6, 0, 0],
          },
        },
      ],
    };
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }
})();
