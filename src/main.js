/**
 * OMEGA Financial Tracker — Client-side engine
 * Drives Chart.js visuals, Mermaid diagrams, and API communication.
 */

// ── State ────────────────────────────────────────────────────────────────────
const state = {
  transactions: [],
  staff: [],
  goals: [],
};

// ── Chart instances ──────────────────────────────────────────────────────────
let lineChart = null;
let doughnutChart = null;

// ── Chart defaults ───────────────────────────────────────────────────────────
Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = '#1f2433';
Chart.defaults.font.family = "'Courier New', monospace";

const PALETTE = [
  '#6366f1','#22c55e','#f59e0b','#ef4444',
  '#3b82f6','#ec4899','#14b8a6','#a855f7',
];

// ── Live clock ───────────────────────────────────────────────────────────────
function startClock() {
  const el = document.getElementById('live-clock');
  const tick = () => {
    el.textContent = new Date().toLocaleString('en-ZA', {
      dateStyle: 'short', timeStyle: 'medium',
    });
  };
  tick();
  setInterval(tick, 1000);
}

// ── API call ─────────────────────────────────────────────────────────────────
async function fetchMetrics() {
  try {
    const res = await fetch('/api/tracker', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        transactions: state.transactions,
        staff: state.staff,
        goals: state.goals,
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('[OMEGA] API unavailable, computing locally:', err.message);
    return computeLocally();
  }
}

// ── Local fallback (mirrors api/tracker.py logic) ────────────────────────────
function computeLocally() {
  let gains = 0, expenses = 0, running = 0;
  const categories = {};
  const timeline = [];

  const sorted = [...state.transactions].sort((a, b) =>
    (a.date || '').localeCompare(b.date || ''));

  for (const tx of sorted) {
    const amt = parseFloat(tx.amount || 0);
    if (tx.type === 'income') {
      gains += amt; running += amt;
    } else {
      expenses += amt; running -= amt;
      const cat = tx.category || 'Uncategorised';
      categories[cat] = (categories[cat] || 0) + amt;
    }
    timeline.push({
      date: tx.date || new Date().toISOString().slice(0,10),
      gains: round2(gains),
      expenses: round2(expenses),
      net: round2(running),
    });
  }

  const staffData = state.staff.map(m => {
    const done = parseInt(m.tasks_completed || 0);
    const assigned = parseInt(m.tasks_assigned || 1);
    return {
      ...m,
      tasks_completed: done,
      tasks_assigned: assigned,
      efficiency: assigned > 0 ? round2((done / assigned) * 100) : 0,
    };
  });

  const net = gains - expenses;
  const goalsData = state.goals.map(g => {
    const target = parseFloat(g.target || 1);
    const progress = Math.min(round2((net / target) * 100), 100);
    return { ...g, current: round2(net), progress, status: progress >= 100 ? 'achieved' : 'in_progress' };
  });

  return {
    metrics: { gains: round2(gains), expenses: round2(expenses), net: round2(net), categories, timeline },
    staff: staffData,
    goals: goalsData,
  };
}

const round2 = v => Math.round(v * 100) / 100;

// ── KPI strip ────────────────────────────────────────────────────────────────
function updateKPIs(metrics) {
  const fmt = n => `R ${n.toLocaleString('en-ZA', { minimumFractionDigits: 2 })}`;
  document.getElementById('kpi-gains').textContent = fmt(metrics.gains);
  document.getElementById('kpi-expenses').textContent = fmt(metrics.expenses);
  const netEl = document.getElementById('kpi-net');
  netEl.textContent = fmt(metrics.net);
  netEl.className = `text-2xl font-bold ${metrics.net >= 0 ? 'text-omega-green' : 'text-omega-red'}`;
}

// ── Line chart ───────────────────────────────────────────────────────────────
function renderLineChart(timeline) {
  const ctx = document.getElementById('lineChart').getContext('2d');
  const labels = timeline.map(t => t.date);
  const datasets = [
    {
      label: 'Income', data: timeline.map(t => t.gains),
      borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,0.08)',
      fill: true, tension: 0.4, pointRadius: 3,
    },
    {
      label: 'Expenses', data: timeline.map(t => t.expenses),
      borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.08)',
      fill: true, tension: 0.4, pointRadius: 3,
    },
    {
      label: 'Net', data: timeline.map(t => t.net),
      borderColor: '#6366f1', backgroundColor: 'rgba(99,102,241,0.08)',
      fill: true, tension: 0.4, pointRadius: 3,
      borderDash: [4, 4],
    },
  ];

  if (lineChart) {
    lineChart.data.labels = labels;
    lineChart.data.datasets = datasets;
    lineChart.update();
    return;
  }

  lineChart = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { boxWidth: 10, padding: 14 } },
        tooltip: { backgroundColor: '#151820', borderColor: '#1f2433', borderWidth: 1 },
      },
      scales: {
        x: { grid: { color: '#1f2433' }, ticks: { maxTicksLimit: 8 } },
        y: { grid: { color: '#1f2433' }, ticks: { callback: v => `R${v}` } },
      },
    },
  });
}

// ── Doughnut chart ───────────────────────────────────────────────────────────
function renderDoughnutChart(categories) {
  const labels = Object.keys(categories);
  const data = Object.values(categories);
  const ctx = document.getElementById('doughnutChart').getContext('2d');

  if (doughnutChart) {
    doughnutChart.data.labels = labels;
    doughnutChart.data.datasets[0].data = data;
    doughnutChart.update();
  } else {
    doughnutChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data,
          backgroundColor: PALETTE,
          borderColor: '#0d0f14',
          borderWidth: 3,
          hoverOffset: 8,
        }],
      },
      options: {
        responsive: true,
        cutout: '68%',
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#151820',
            borderColor: '#1f2433',
            borderWidth: 1,
            callbacks: {
              label: ctx => ` R ${ctx.parsed.toLocaleString('en-ZA', { minimumFractionDigits: 2 })}`,
            },
          },
        },
      },
    });
  }

  // Custom legend
  const legendEl = document.getElementById('cat-legend');
  legendEl.innerHTML = labels.map((lbl, i) => `
    <span class="flex items-center gap-1">
      <span style="background:${PALETTE[i % PALETTE.length]};width:8px;height:8px;border-radius:2px;display:inline-block"></span>
      <span style="color:#94a3b8">${lbl}</span>
    </span>
  `).join('');
}

// ── Mermaid: Staff & Bridges ─────────────────────────────────────────────────
function renderMermaidDiagram(staffList) {
  mermaid.initialize({
    startOnLoad: false,
    theme: 'dark',
    themeVariables: {
      primaryColor: '#1f2433',
      primaryTextColor: '#e2e8f0',
      primaryBorderColor: '#6366f1',
      lineColor: '#6366f1',
      fontFamily: 'Courier New, monospace',
      fontSize: '12px',
    },
  });

  const container = document.getElementById('mermaid-chart');

  if (staffList.length === 0) {
    container.innerHTML = `<p class="text-omega-muted text-xs text-center py-6">Add team members to generate the org diagram.</p>`;
    return;
  }

  const nodes = staffList.map((m, i) => {
    const eff = m.efficiency ?? 0;
    const effColor = eff >= 80 ? '✅' : eff >= 50 ? '⚠️' : '❌';
    return `  M${i}["${m.name}<br/><small>${m.role}</small><br/>${effColor} ${eff}% efficiency"]`;
  });

  const edges = staffList.map((m, i) => {
    if (i === 0) return '';
    const bridge = m.milestones && m.milestones.length > 0
      ? m.milestones[0]
      : `${m.tasks_completed}/${m.tasks_assigned} tasks`;
    return `  M0 -->|"${bridge}"| M${i}`;
  });

  const chart = `graph TD\n  M0_label["🏢 Project Lead"]\n${nodes.join('\n')}\n${edges.filter(Boolean).join('\n')}\n  M0_label --> M0`;

  container.innerHTML = `<div class="mermaid">${chart}</div>`;

  mermaid.run({ nodes: container.querySelectorAll('.mermaid') });
}

// ── Goals list ───────────────────────────────────────────────────────────────
function renderGoals(goalsData) {
  const el = document.getElementById('goals-list');
  if (goalsData.length === 0) {
    el.innerHTML = `<p class="text-omega-muted text-xs">No goals yet. Add one above.</p>`;
    return;
  }
  el.innerHTML = goalsData.map(g => `
    <div class="bg-omega-bg border border-omega-border rounded-lg p-3">
      <div class="flex justify-between items-center">
        <span class="text-xs font-semibold">${g.name}</span>
        <span class="text-xs ${g.status === 'achieved' ? 'text-omega-green' : 'text-omega-yellow'}">
          ${g.status === 'achieved' ? '✓ Achieved' : `${g.progress}%`}
        </span>
      </div>
      <div class="text-omega-muted text-xs mt-1">
        R ${(g.current || 0).toLocaleString('en-ZA', {minimumFractionDigits: 2})} 
        / R ${parseFloat(g.target).toLocaleString('en-ZA', {minimumFractionDigits: 2})}
      </div>
      <div class="goal-bar-track">
        <div class="goal-bar-fill" style="width: ${g.progress}%"></div>
      </div>
    </div>
  `).join('');
}

// ── Full render cycle ────────────────────────────────────────────────────────
async function refresh() {
  const data = await fetchMetrics();
  updateKPIs(data.metrics);

  if (data.metrics.timeline.length > 0) {
    renderLineChart(data.metrics.timeline);
  }

  if (Object.keys(data.metrics.categories).length > 0) {
    renderDoughnutChart(data.metrics.categories);
  }

  renderMermaidDiagram(data.staff);
  renderGoals(data.goals);
}

// ── Public action handlers (called by HTML onclick) ──────────────────────────
window.addTransaction = function () {
  const desc = document.getElementById('tx-desc').value.trim();
  const amount = parseFloat(document.getElementById('tx-amount').value);
  const type = document.getElementById('tx-type').value;
  const category = document.getElementById('tx-category').value.trim() || 'Uncategorised';

  if (!desc || isNaN(amount) || amount <= 0) {
    alert('Please enter a valid description and amount.');
    return;
  }

  state.transactions.push({
    description: desc,
    amount,
    type,
    category,
    date: new Date().toISOString().slice(0, 10),
  });

  document.getElementById('tx-desc').value = '';
  document.getElementById('tx-amount').value = '';
  document.getElementById('tx-category').value = '';
  refresh();
};

window.addGoal = function () {
  const name = document.getElementById('goal-name').value.trim();
  const target = parseFloat(document.getElementById('goal-target').value);

  if (!name || isNaN(target) || target <= 0) {
    alert('Please enter a valid goal name and target amount.');
    return;
  }

  state.goals.push({ name, target });
  document.getElementById('goal-name').value = '';
  document.getElementById('goal-target').value = '';
  refresh();
};

window.addStaff = function () {
  const name = document.getElementById('staff-name').value.trim();
  const role = document.getElementById('staff-role').value.trim();
  const assigned = parseInt(document.getElementById('staff-assigned').value) || 0;
  const done = parseInt(document.getElementById('staff-done').value) || 0;

  if (!name || !role) {
    alert('Please enter a name and role.');
    return;
  }

  state.staff.push({
    name,
    role,
    tasks_assigned: assigned,
    tasks_completed: Math.min(done, assigned),
    milestones: [],
  });

  document.getElementById('staff-name').value = '';
  document.getElementById('staff-role').value = '';
  document.getElementById('staff-assigned').value = '';
  document.getElementById('staff-done').value = '';
  refresh();
};

// ── Seed demo data ───────────────────────────────────────────────────────────
function seedDemo() {
  const today = new Date();
  const daysAgo = n => {
    const d = new Date(today);
    d.setDate(d.getDate() - n);
    return d.toISOString().slice(0, 10);
  };

  state.transactions = [
    { description: 'Salary', amount: 35000, type: 'income', category: 'Income', date: daysAgo(30) },
    { description: 'Rent', amount: 9500, type: 'expense', category: 'Housing', date: daysAgo(29) },
    { description: 'Groceries', amount: 2200, type: 'expense', category: 'Food', date: daysAgo(25) },
    { description: 'Freelance payment', amount: 8000, type: 'income', category: 'Income', date: daysAgo(20) },
    { description: 'Electricity', amount: 1100, type: 'expense', category: 'Utilities', date: daysAgo(18) },
    { description: 'Internet', amount: 700, type: 'expense', category: 'Utilities', date: daysAgo(17) },
    { description: 'Petrol', amount: 1800, type: 'expense', category: 'Transport', date: daysAgo(14) },
    { description: 'Restaurant', amount: 950, type: 'expense', category: 'Food', date: daysAgo(10) },
    { description: 'Side project', amount: 3000, type: 'income', category: 'Income', date: daysAgo(7) },
    { description: 'Clothing', amount: 1500, type: 'expense', category: 'Shopping', date: daysAgo(4) },
    { description: 'Salary', amount: 35000, type: 'income', category: 'Income', date: daysAgo(0) },
  ];

  state.staff = [
    { name: 'Lerato M.', role: 'Project Lead', tasks_assigned: 10, tasks_completed: 10, milestones: ['Q1 Review'] },
    { name: 'Sipho D.', role: 'Developer', tasks_assigned: 15, tasks_completed: 13, milestones: ['API Integration'] },
    { name: 'Ayasha K.', role: 'Designer', tasks_assigned: 8, tasks_completed: 7, milestones: ['UI Refresh'] },
    { name: 'Thabo N.', role: 'Analyst', tasks_assigned: 12, tasks_completed: 6, milestones: ['Q2 Report'] },
  ];

  state.goals = [
    { name: 'Emergency Fund', target: 50000 },
    { name: 'Holiday Trip', target: 20000 },
    { name: 'New Laptop', target: 25000 },
  ];
}

// ── Boot ─────────────────────────────────────────────────────────────────────
startClock();
seedDemo();
refresh();
