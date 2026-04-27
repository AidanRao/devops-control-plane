(function () {
  "use strict";

  const API_BASE = ""; // 与 FastAPI 部署在同一域名下
  const FOLLOW_INTERVAL_MS = 1500;
  const FOLLOW_MAX_DURATION_MS = 5 * 60 * 1000;

  let statusChart = null;
  let followTimer = null;
  let followTaskId = null;
  let followStartedAt = 0;
  let autoFollowEnabled = true;
  let lastCommandText = "";

  document.addEventListener("DOMContentLoaded", function () {
    initTheme();
    initThemeToggle();
    initAgentsSection();
    initCommandSection();
    initTaskSection();
    initAutoFollowToggle();
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
      return;
    }

    empty.classList.add("hidden");
    countEl.textContent = String(agents.length);

    agents.forEach(function (agent) {
      const tr = document.createElement("tr");
      tr.className =
        "bg-white/60 odd:bg-white/80 dark:bg-slate-900/40 odd:dark:bg-slate-900/60";

      // 设备 ID（合并 DeviceToken 状态到前缀小圆点）
      const idCell = document.createElement("td");
      idCell.className = "px-4 py-2 text-xs";
      const idWrap = document.createElement("div");
      idWrap.className = "flex items-center gap-2";

      const dot = document.createElement("span");
      dot.className =
        "inline-block h-2 w-2 flex-none rounded-full " +
        (agent.hasDeviceToken
          ? "bg-emerald-500"
          : "bg-slate-300 dark:bg-slate-600");
      dot.title = agent.hasDeviceToken
        ? "已配置 DeviceToken"
        : "未配置 DeviceToken";
      dot.setAttribute(
        "aria-label",
        agent.hasDeviceToken ? "已配置 DeviceToken" : "未配置 DeviceToken"
      );
      idWrap.appendChild(dot);

      const idText = document.createElement("span");
      idText.className =
        "truncate font-mono text-slate-800 dark:text-slate-100";
      idText.textContent = agent.device_id || "-";
      idText.title = agent.device_id || "";
      idWrap.appendChild(idText);
      idCell.appendChild(idWrap);
      tr.appendChild(idCell);

      // 心跳（右对齐）
      const hbCell = document.createElement("td");
      hbCell.className =
        "px-4 py-2 text-right text-xs text-slate-600 dark:text-slate-300";
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
      statusEl.className = "text-xs text-rose-500 dark:text-rose-300";
      return;
    }

    statusEl.textContent = "正在下发命令...";
    statusEl.className = "text-xs text-slate-500 dark:text-slate-400";

    lastCommandText = command;
    stopFollow();
    renderTerminalPreview(command);

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
      statusEl.className = "text-xs text-emerald-600 dark:text-emerald-300";

      if (taskIdInput) {
        taskIdInput.value = taskId;
      }

      // 自动开始加载结果（按需跟随）
      if (autoFollowEnabled) {
        startFollow(taskId);
      } else {
        fetchTask(taskId);
      }
    } catch (err) {
      console.error("下发命令失败", err);
      statusEl.textContent = "下发命令失败，请稍后重试或检查服务端日志。";
      statusEl.className = "text-xs text-rose-500 dark:text-rose-300";
    }
  }

  // ---------- 自动跟随开关 ----------
  function initAutoFollowToggle() {
    const btn = document.getElementById("autoFollowBtn");
    if (!btn) return;
    updateAutoFollowUi();
    btn.addEventListener("click", function () {
      autoFollowEnabled = !autoFollowEnabled;
      updateAutoFollowUi();
      if (!autoFollowEnabled) {
        stopFollow();
      } else if (followTaskId) {
        startFollow(followTaskId);
      } else {
        const input = document.getElementById("taskIdInput");
        const id = input ? input.value.trim() : "";
        if (id) startFollow(id);
      }
    });
  }

  function updateAutoFollowUi() {
    const icon = document.getElementById("autoFollowIcon");
    const label = document.getElementById("autoFollowLabel");
    if (icon) {
      icon.textContent = autoFollowEnabled ? "pause_circle" : "play_circle";
    }
    if (label) {
      label.textContent = autoFollowEnabled ? "停止跟随" : "自动跟随";
    }
  }

  function startFollow(taskId) {
    stopFollow();
    if (!taskId) return;
    followTaskId = taskId;
    followStartedAt = Date.now();
    fetchTask(taskId, true);
  }

  function stopFollow() {
    if (followTimer) {
      window.clearTimeout(followTimer);
      followTimer = null;
    }
    followTaskId = null;
  }

  function scheduleFollow(taskId) {
    if (!autoFollowEnabled) return;
    if (followTaskId !== taskId) return;
    if (Date.now() - followStartedAt > FOLLOW_MAX_DURATION_MS) {
      stopFollow();
      return;
    }
    followTimer = window.setTimeout(function () {
      fetchTask(taskId, true);
    }, FOLLOW_INTERVAL_MS);
  }

  // ---------- 任务查询 & 终端渲染 ----------
  function initTaskSection() {
    const btn = document.getElementById("queryTaskBtn");
    if (btn) {
      btn.addEventListener("click", function () {
        const input = document.getElementById("taskIdInput");
        if (!input) return;
        const taskId = input.value.trim();
        if (!taskId) {
          const statusEl = document.getElementById("taskStatusText");
          if (statusEl) {
            statusEl.textContent = "请先填写 task_uuid。";
            statusEl.className = "text-xs text-rose-500 dark:text-rose-300";
          }
          return;
        }
        if (autoFollowEnabled) {
          startFollow(taskId);
        } else {
          stopFollow();
          fetchTask(taskId);
        }
      });
    }

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

  async function fetchTask(taskId, isFollow) {
    const statusEl = document.getElementById("taskStatusText");
    if (!isFollow) {
      if (statusEl) {
        statusEl.textContent = "正在查询任务...";
        statusEl.className = "text-xs text-slate-500 dark:text-slate-400";
      }
    }

    try {
      const res = await fetch(
        `${API_BASE}/api/commands/${encodeURIComponent(taskId)}`
      );
      if (!res.ok) {
        if (res.status === 404) {
          if (statusEl) {
            statusEl.textContent = "未找到对应 task_uuid 的任务。";
            statusEl.className = "text-xs text-rose-500 dark:text-rose-300";
          }
          stopFollow();
          if (statusChart) {
            statusChart.setOption(baseChartOption([], []));
          }
          renderTerminalEmpty(
            "未找到对应 task_uuid 的任务，请确认是否已下发。"
          );
          return;
        }
        const text = await res.text();
        throw new Error(`HTTP ${res.status}: ${text}`);
      }

      const data = await res.json();
      renderTask(data, { isFollow: !!isFollow, taskId: taskId });

      if (isFollow && shouldKeepFollowing(data)) {
        scheduleFollow(taskId);
      } else if (isFollow) {
        stopFollow();
      }
    } catch (err) {
      console.error("查询任务失败", err);
      if (statusEl) {
        statusEl.textContent = "查询失败，请稍后重试。";
        statusEl.className = "text-xs text-rose-500 dark:text-rose-300";
      }
      stopFollow();
      if (statusChart) {
        statusChart.setOption(baseChartOption([], []));
      }
    }
  }

  function shouldKeepFollowing(data) {
    const status = (data && data.status) || "";
    if (!status || status === "Pending" || status === "Dispatching") return true;
    const results = Array.isArray(data.results) ? data.results : [];
    if (!results.length) return true;
    const hasRunning = results.some(function (item) {
      return (item && item.status) === "Running";
    });
    return hasRunning;
  }

  function renderTask(data, ctx) {
    const statusEl = document.getElementById("taskStatusText");
    const metaEl = document.getElementById("taskMetaText");
    const entries = Array.isArray(data.results) ? data.results : [];

    if (statusEl) {
      statusEl.textContent = `任务状态：${data.status || "未知"}`;
      statusEl.className = "text-xs text-slate-600 dark:text-slate-300";
    }
    if (metaEl) {
      const parts = [];
      if (data.task_uuid) parts.push(`task_uuid: ${data.task_uuid}`);
      parts.push(`agent: ${entries.length}`);
      if (ctx && ctx.isFollow) parts.push("自动跟随中");
      metaEl.textContent = parts.join("  ·  ");
    }

    const statusCounts = {};
    entries.forEach(function (item) {
      const s = normalizeAgentStatus(item);
      statusCounts[s] = (statusCounts[s] || 0) + 1;
    });

    if (statusChart) {
      const categories = Object.keys(statusCounts);
      const values = categories.map(function (k) {
        return statusCounts[k] || 0;
      });
      statusChart.setOption(baseChartOption(categories, values));
    }

    renderTerminal(data, entries, ctx || {});
  }

  // ---------- 终端渲染 ----------
  function renderTerminalPreview(command) {
    const host = document.getElementById("terminalOutput");
    const countEl = document.getElementById("terminalAgentCount");
    if (!host) return;
    if (countEl) countEl.textContent = "0 agent";
    host.innerHTML = "";
    const block = document.createElement("div");
    block.className = "terminal-block";
    block.innerHTML =
      buildPromptLine("local", command) +
      `<div class="stream-meta">等待 Agent 接收并返回结果…<span class="cursor"></span></div>`;
    host.appendChild(block);
  }

  function renderTerminalEmpty(text) {
    const host = document.getElementById("terminalOutput");
    const countEl = document.getElementById("terminalAgentCount");
    if (!host) return;
    if (countEl) countEl.textContent = "0 agent";
    host.innerHTML = `<div class="terminal-empty text-slate-500">${escapeHtml(
      text
    )}</div>`;
  }

  function renderTerminal(data, entries, ctx) {
    const host = document.getElementById("terminalOutput");
    const countEl = document.getElementById("terminalAgentCount");
    if (!host) return;

    if (countEl) {
      countEl.textContent = `${entries.length} agent`;
    }

    const prevScrollTop = host.scrollTop;
    const prevScrollHeight = host.scrollHeight;
    const isAtBottom =
      prevScrollHeight - (prevScrollTop + host.clientHeight) < 24;

    const commandText =
      data.command || lastCommandText || getCommandInputValue() || "(command)";

    host.innerHTML = "";

    if (!entries.length) {
      const block = document.createElement("div");
      block.className = "terminal-block";
      block.innerHTML =
        buildPromptLine("local", commandText) +
        `<div class="stream-meta">任务已创建，等待 Agent 返回结果…<span class="cursor"></span></div>`;
      host.appendChild(block);
      scrollTerminal(host, isAtBottom, prevScrollTop);
      return;
    }

    entries.forEach(function (item) {
      const agentId = item && item.agent_id ? item.agent_id : "unknown";
      const normalized = normalizeAgentStatus(item);
      const block = document.createElement("div");
      block.className = "terminal-block";

      const header = document.createElement("div");
      header.className = "terminal-header";
      header.innerHTML =
        `<span class="terminal-agent">${escapeHtml(agentId)}</span>` +
        `<span class="terminal-status status-${normalized.toLowerCase()}">${escapeHtml(
          normalized
        )}</span>` +
        (typeof item.exitCode === "number"
          ? `<span>exit ${escapeHtml(String(item.exitCode))}</span>`
          : "");
      block.appendChild(header);

      const prompt = document.createElement("div");
      prompt.innerHTML = buildPromptLine(agentId, commandText);
      block.appendChild(prompt);

      const stdout = renderStreamBlock(item.stdout, "stdout");
      if (stdout) block.appendChild(stdout);

      const stderr = renderStreamBlock(item.stderr, "stderr");
      if (stderr) block.appendChild(stderr);

      if (normalized === "Running") {
        const running = document.createElement("div");
        running.className = "stream-meta";
        running.innerHTML = "执行中…<span class='cursor'></span>";
        block.appendChild(running);
      } else if (!stdout && !stderr) {
        const empty = document.createElement("div");
        empty.className = "stream-meta";
        empty.textContent = "(无输出)";
        block.appendChild(empty);
      }

      host.appendChild(block);
    });

    scrollTerminal(host, isAtBottom, prevScrollTop);
  }

  function buildPromptLine(agent, command) {
    return (
      `<div>` +
      `<span class="prompt">${escapeHtml(agent)} $</span>` +
      `<span class="stream-stdout">${escapeHtml(command)}</span>` +
      `</div>`
    );
  }

  function renderStreamBlock(text, kind) {
    if (text === null || text === undefined) return null;
    const str = String(text);
    if (!str.length) return null;
    const pre = document.createElement("pre");
    pre.className = kind === "stderr" ? "stream-stderr" : "stream-stdout";
    pre.innerHTML = ansiToHtml(str);
    return pre;
  }

  function scrollTerminal(host, isAtBottom, prevScrollTop) {
    if (isAtBottom) {
      host.scrollTop = host.scrollHeight;
    } else {
      host.scrollTop = prevScrollTop;
    }
  }

  function getCommandInputValue() {
    const el = document.getElementById("commandInput");
    return el ? el.value.trim() : "";
  }

  // ---------- 终端输出的 ANSI 着色 ----------
  const ANSI_COLOR_MAP = {
    30: "#1f2937",
    31: "#f87171",
    32: "#34d399",
    33: "#fbbf24",
    34: "#60a5fa",
    35: "#c084fc",
    36: "#22d3ee",
    37: "#e2e8f0",
    90: "#94a3b8",
    91: "#fb7185",
    92: "#4ade80",
    93: "#facc15",
    94: "#93c5fd",
    95: "#e879f9",
    96: "#67e8f9",
    97: "#f8fafc",
  };

  function ansiToHtml(text) {
    const escaped = escapeHtml(text);
    const ansiRegex = /\u001b\[([0-9;]*)m/g;
    let result = "";
    let lastIndex = 0;
    let openSpan = false;
    let match;
    while ((match = ansiRegex.exec(escaped)) !== null) {
      result += escaped.slice(lastIndex, match.index);
      const codes = match[1].split(";").filter(Boolean).map(Number);
      if (openSpan) {
        result += "</span>";
        openSpan = false;
      }
      const styles = [];
      codes.forEach(function (code) {
        if (code === 0 || Number.isNaN(code)) return;
        if (code === 1) styles.push("font-weight:600");
        else if (code === 3) styles.push("font-style:italic");
        else if (code === 4) styles.push("text-decoration:underline");
        else if (ANSI_COLOR_MAP[code])
          styles.push(`color:${ANSI_COLOR_MAP[code]}`);
      });
      if (styles.length) {
        result += `<span style="${styles.join(";")}">`;
        openSpan = true;
      }
      lastIndex = ansiRegex.lastIndex;
    }
    result += escaped.slice(lastIndex);
    if (openSpan) result += "</span>";
    return result;
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

  function baseChartOption(categories, values) {
    return {
      grid: { left: 32, right: 16, top: 24, bottom: 26 },
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
