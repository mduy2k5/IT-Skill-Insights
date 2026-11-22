// Global state and ECharts instances (Light Theme)
const state = {
  currentTrack: 'all',
  data: null,
  selectedRoleFamily: null,
  roleChart: null,
  levelChart: null,
  heatmapChart: null,
};

function number(val) {
  return new Intl.NumberFormat('vi-VN').format(Number(val) || 0);
}

function node(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined && text !== null) el.textContent = String(text);
  return el;
}

// -------------------------------------------------------------
// 1. Fetch & Controller
// -------------------------------------------------------------
async function loadDashboardData(track = 'all') {
  const badge = document.getElementById('dataset-badge');
  badge.textContent = 'Đang đồng bộ OLAP...';

  try {
    const res = await fetch(`/api/analyst/insights?track=${encodeURIComponent(track)}`);
    if (!res.ok) throw new Error(`Lỗi kết nối API: ${res.status}`);
    const data = await res.json();
    state.data = data;

    renderKPIs(data);
    renderRoleChart(data.role_groups);
    renderLevelChart(data.all_levels);
    renderHeatmap(data.role_groups, data.all_levels);
    renderRoleSelector(data.role_groups);

    badge.textContent = `${number(data.total_jobs)} Job · DuckDB OLAP`;
  } catch (err) {
    console.error(err);
    badge.textContent = 'Lỗi kết nối';
  }
}

// -------------------------------------------------------------
// 2. Render KPI Stats
// -------------------------------------------------------------
function renderKPIs(data) {
  document.getElementById('kpi-jobs').textContent = number(data.total_jobs);
  document.getElementById('kpi-roles').textContent = number(data.role_groups.length);

  // Calculate unique skills count across all roles
  const skillSet = new Set();
  data.role_groups.forEach(rg => {
    rg.all_skills.forEach(s => skillSet.add(s.skill));
  });
  document.getElementById('kpi-skills').textContent = number(skillSet.size);
}

// -------------------------------------------------------------
// 3. ECharts: Bar Chart - Role Family Distribution (Light Theme)
// -------------------------------------------------------------
function renderRoleChart(groups) {
  const dom = document.getElementById('chart-roles');
  if (!dom) return;

  if (!state.roleChart) {
    state.roleChart = echarts.init(dom, null, { renderer: 'canvas' });
  }

  // Take top 10 role families
  const topGroups = groups.slice(0, 10).reverse();
  const yData = topGroups.map(g => g.role_family.length > 25 ? g.role_family.slice(0, 23) + '...' : g.role_family);
  const xData = topGroups.map(g => g.job_count);

  const option = {
    backgroundColor: '#ffffff',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: '{b}: <strong>{c} jobs</strong>'
    },
    grid: { left: '3%', right: '8%', bottom: '3%', top: '3%', containLabel: true },
    xAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f1f5f9' } },
      axisLabel: { color: '#64748b' }
    },
    yAxis: {
      type: 'category',
      data: yData,
      axisLabel: { color: '#1e293b', fontSize: 11, fontWeight: 500 },
      axisLine: { lineStyle: { color: '#cbd5e1' } }
    },
    series: [
      {
        type: 'bar',
        data: xData,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: '#3b82f6' },
            { offset: 1, color: '#0284c7' }
          ]),
          borderRadius: [0, 4, 4, 0]
        },
        label: {
          show: true,
          position: 'right',
          color: '#1e40af',
          fontWeight: 'bold',
          fontSize: 11
        }
      }
    ]
  };

  // Click bar to filter or select role
  state.roleChart.on('click', params => {
    if (params.name) {
      state.selectedRoleFamily = params.name;
      const select = document.getElementById('role-family-select');
      if (select) select.value = params.name;
      if (state.data && state.data.role_groups) {
        updateRolePills(state.data.role_groups);
        renderSingleRoleDetails(state.data.role_groups);
      }
      const roleSection = document.querySelector('.role-explorer-section');
      if (roleSection) roleSection.scrollIntoView({ behavior: 'smooth' });
    }
  });

  state.roleChart.setOption(option);
}

// -------------------------------------------------------------
// 4. ECharts: Donut Chart - Level Distribution (Light Theme)
// -------------------------------------------------------------
function renderLevelChart(levels) {
  const dom = document.getElementById('chart-levels');
  if (!dom) return;

  if (!state.levelChart) {
    state.levelChart = echarts.init(dom, null, { renderer: 'canvas' });
  }

  const pieData = levels.map(l => ({ name: l.level, value: l.job_count }));

  const option = {
    backgroundColor: '#ffffff',
    color: ['#2563eb', '#0284c7', '#0d9488', '#16a34a', '#ca8a04', '#ea580c', '#9333ea', '#64748b'],
    tooltip: {
      trigger: 'item',
      formatter: '{b}: <strong>{c} jobs</strong> ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: '4%',
      top: 'center',
      textStyle: { color: '#475569', fontSize: 11 }
    },
    series: [
      {
        name: 'Level',
        type: 'pie',
        radius: ['45%', '72%'],
        center: ['35%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 6,
          borderColor: '#ffffff',
          borderWidth: 2
        },
        label: { show: false },
        emphasis: {
          label: {
            show: true,
            fontSize: 13,
            fontWeight: 'bold',
            color: '#0f172a'
          }
        },
        data: pieData
      }
    ]
  };

  state.levelChart.setOption(option);
}

// -------------------------------------------------------------
// 5. ECharts: Heatmap - Skill x Level Matrix (Light Theme)
// -------------------------------------------------------------
function renderHeatmap(groups, allLevels) {
  const dom = document.getElementById('chart-heatmap');
  if (!dom) return;

  if (!state.heatmapChart) {
    state.heatmapChart = echarts.init(dom, null, { renderer: 'canvas' });
  }

  // Filter top levels (exclude trivial)
  const levels = allLevels.map(l => l.level).slice(0, 6);

  // Get top 15 most frequent skills overall
  const skillCountMap = {};
  groups.forEach(g => {
    g.all_skills.forEach(s => {
      skillCountMap[s.skill] = (skillCountMap[s.skill] || 0) + s.job_count;
    });
  });

  const topSkills = Object.entries(skillCountMap)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 15)
    .map(x => x[0])
    .reverse();

  // Build matrix data: [x_level_index, y_skill_index, value]
  const matrixData = [];
  let maxVal = 1;

  levels.forEach((lvl, xIdx) => {
    topSkills.forEach((sk, yIdx) => {
      let count = 0;
      groups.forEach(g => {
        const lvlData = g.level_skills.find(l => l.level === lvl);
        if (lvlData) {
          const skData = lvlData.all_skills.find(s => s.skill === sk);
          if (skData) count += skData.job_count;
        }
      });
      if (count > maxVal) maxVal = count;
      matrixData.push([xIdx, yIdx, count]);
    });
  });

  const option = {
    backgroundColor: '#ffffff',
    tooltip: {
      position: 'top',
      formatter: function (params) {
        const lvl = levels[params.value[0]];
        const sk = topSkills[params.value[1]];
        const val = params.value[2];
        return `<strong>${sk}</strong><br/>Cấp bậc: ${lvl}<br/>Nhu cầu: <strong>${val} jobs</strong>`;
      }
    },
    grid: { left: '14%', right: '5%', bottom: '10%', top: '4%' },
    xAxis: {
      type: 'category',
      data: levels,
      splitArea: { show: true, areaStyle: { color: ['#ffffff', '#f8fafc'] } },
      axisLabel: { color: '#0369a1', fontSize: 12, fontWeight: 'bold' },
      axisLine: { lineStyle: { color: '#cbd5e1' } }
    },
    yAxis: {
      type: 'category',
      data: topSkills,
      splitArea: { show: true, areaStyle: { color: ['#ffffff', '#f8fafc'] } },
      axisLabel: { color: '#1e293b', fontSize: 11, fontWeight: 500 },
      axisLine: { lineStyle: { color: '#cbd5e1' } }
    },
    visualMap: {
      min: 0,
      max: maxVal,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: '0%',
      inRange: {
        color: ['#f1f5f9', '#bae6fd', '#38bdf8', '#0284c7', '#0369a1']
      },
      textStyle: { color: '#64748b' }
    },
    series: [
      {
        name: 'Skill-Level Demand',
        type: 'heatmap',
        data: matrixData,
        label: {
          show: true,
          formatter: function (p) {
            return p.value[2] > 0 ? p.value[2] : '';
          },
          color: '#0f172a',
          fontSize: 11,
          fontWeight: 'bold'
        },
        itemStyle: {
          borderWidth: 1,
          borderColor: '#ffffff'
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 8,
            shadowColor: 'rgba(0, 0, 0, 0.15)'
          }
        }
      }
    ]
  };

  state.heatmapChart.setOption(option);
}

// -------------------------------------------------------------
// 6. Role Selection & Detailed Skill View (Dropdown / Pill selector)
// -------------------------------------------------------------
function renderRoleSelector(groups) {
  const select = document.getElementById('role-family-select');
  const pillsBar = document.getElementById('role-pills-bar');
  if (!select || !groups || groups.length === 0) return;

  // Preserve previous selection if available in current groups, otherwise choose top 1
  const existingRole = groups.find(g => g.role_family === state.selectedRoleFamily);
  if (!existingRole) {
    state.selectedRoleFamily = groups[0].role_family;
  }

  // Populate Select
  select.innerHTML = '';
  groups.forEach(g => {
    const opt = document.createElement('option');
    opt.value = g.role_family;
    opt.textContent = `${g.role_family} (${g.job_count} jobs)`;
    if (g.role_family === state.selectedRoleFamily) opt.selected = true;
    select.appendChild(opt);
  });

  // Populate Quick Filter Pills
  if (pillsBar) {
    pillsBar.innerHTML = '';
    groups.slice(0, 10).forEach(g => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'track-btn' + (g.role_family === state.selectedRoleFamily ? ' active' : '');
      btn.style.fontSize = '0.8rem';
      btn.style.padding = '5px 12px';
      btn.textContent = `${g.role_family} (${g.job_count})`;
      btn.addEventListener('click', () => {
        state.selectedRoleFamily = g.role_family;
        select.value = g.role_family;
        updateRolePills(groups);
        renderSingleRoleDetails(groups);
      });
      pillsBar.appendChild(btn);
    });
  }

  select.onchange = (e) => {
    state.selectedRoleFamily = e.target.value;
    updateRolePills(groups);
    renderSingleRoleDetails(groups);
  };

  renderSingleRoleDetails(groups);
}

function updateRolePills(groups) {
  const pillsBar = document.getElementById('role-pills-bar');
  if (!pillsBar) return;
  pillsBar.querySelectorAll('button').forEach(btn => {
    if (btn.textContent.startsWith(state.selectedRoleFamily)) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
}

function renderSingleRoleDetails(groups) {
  const container = document.getElementById('role-skills-container');
  if (!container) return;

  const group = groups.find(g => g.role_family === state.selectedRoleFamily) || groups[0];
  if (!group) {
    container.innerHTML = '<p class="scope-note">Không tìm thấy dữ liệu cho nhóm nghề này.</p>';
    return;
  }

  const card = document.createElement('div');
  card.className = 'role-skill-group';
  card.style.border = '1px solid #cbd5e1';
  card.style.borderRadius = '12px';
  card.style.boxShadow = '0 2px 4px rgba(0, 0, 0, 0.03)';

  const header = node('div', 'role-skill-content', '');
  header.style.padding = '18px 24px';
  header.style.background = '#f8fafc';
  header.style.borderBottom = '1px solid var(--card-border)';
  header.style.display = 'flex';
  header.style.justifyContent = 'space-between';
  header.style.alignItems = 'center';
  header.style.flexWrap = 'wrap';
  header.style.gap = '12px';

  const titleWrap = document.createElement('div');
  const h2 = node('h2', '', `💼 Họ nghề: ${group.role_family}`);
  h2.style.fontSize = '1.25rem';
  h2.style.fontWeight = '800';
  h2.style.color = '#0f172a';
  h2.style.margin = '0 0 4px 0';

  const subtitle = node('p', '', `Tổng cộng ${number(group.job_count)} tin tuyển dụng · ${number(group.unique_skill_count)} kỹ năng khác nhau được nhận diện`);
  subtitle.style.fontSize = '0.85rem';
  subtitle.style.color = '#64748b';
  subtitle.style.margin = '0';
  titleWrap.append(h2, subtitle);

  const badge = node('span', 'local-badge', `JobBERT V3 Normalized`);
  badge.style.fontSize = '0.75rem';
  header.append(titleWrap, badge);

  const content = node('div', 'role-skill-content');
  content.style.padding = '22px 24px';

  // 1. Core Skills Tag Cloud
  const q1Title = node('h3', 'sub-section-title', '1. Kỹ năng trọng tâm & phổ biến nhất');
  const tagCloud = node('div', 'skills-tag-cloud');
  if (group.top_skills && group.top_skills.length) {
    group.top_skills.forEach(sk => {
      const pill = node('span', 'skill-pill');
      pill.append(
        node('span', '', sk.skill),
        node('strong', '', `${sk.job_count} job`)
      );
      tagCloud.append(pill);
    });
  } else {
    tagCloud.append(node('p', 'scope-note', 'Chưa có tag kỹ năng từ nguồn cho nhóm này.'));
  }
  content.append(q1Title, tagCloud);

  // 2. Level Matrix
  const q2Title = node('h3', 'sub-section-title', '2. Phân hóa kỹ năng theo từng cấp bậc (Level)');
  content.append(q2Title);

  if (group.level_skills && group.level_skills.length) {
    const levelGrid = node('div', 'level-matrix-grid');
    group.level_skills.forEach(lvl => {
      const lvlCard = node('div', 'level-matrix-card');
      const lvlHeader = node('div', 'level-card-header');
      lvlHeader.append(
        node('span', 'level-card-name', `🎯 ${lvl.level}`),
        node('span', 'level-card-count', `${lvl.job_count} job`)
      );
      lvlCard.append(lvlHeader);

      const skillList = node('ul', 'level-skill-list');
      if (lvl.top_skills && lvl.top_skills.length) {
        const maxCount = Math.max(...lvl.top_skills.map(s => s.job_count), 1);
        lvl.top_skills.forEach(sk => {
          const row = node('li', 'level-skill-row');
          row.append(node('span', '', sk.skill));

          const barWrap = node('div', 'skill-bar-wrap');
          const bg = node('div', 'skill-bar-bg');
          const fill = node('div', 'skill-bar-fill');
          fill.style.width = `${Math.min(100, Math.round((sk.job_count / maxCount) * 100))}%`;
          bg.append(fill);
          barWrap.append(bg, node('strong', '', `${sk.job_count}`));
          row.append(barWrap);

          skillList.append(row);
        });
      } else {
        skillList.append(node('li', 'scope-note', 'Chưa có tag skill'));
      }
      lvlCard.append(skillList);
      levelGrid.append(lvlCard);
    });
    content.append(levelGrid);
  } else {
    content.append(node('p', 'scope-note', 'Nhóm này chưa có phân loại level.'));
  }

  // 3. Raw Job Titles for Verification
  const jobListDetails = document.createElement('details');
  jobListDetails.style.marginTop = '20px';
  jobListDetails.style.background = '#f8fafc';
  jobListDetails.style.padding = '12px 16px';
  jobListDetails.style.borderRadius = '8px';
  jobListDetails.style.border = '1px solid #e2e8f0';

  const jobSummary = document.createElement('summary');
  jobSummary.style.fontSize = '0.85rem';
  jobSummary.style.fontWeight = '600';
  jobSummary.style.color = '#334155';
  jobSummary.style.cursor = 'pointer';
  jobSummary.textContent = `📋 Xem danh sách ${group.jobs.length} tin tuyển dụng gốc thuộc họ nghề này`;

  const jobUl = node('ul', 'topic-jobs');
  jobUl.style.marginTop = '10px';
  group.jobs.forEach(j => {
    const li = node('li', '');
    const conf = j.confidence ? ` (độ tin cậy: ${(j.confidence * 100).toFixed(1)}%)` : '';
    const lvl = j.levels.length ? ` [${j.levels.join(', ')}]` : '';
    li.append(
      node('span', 'topic-job-id', j.job_id),
      node('span', '', `${j.title}${lvl}${conf}`)
    );
    jobUl.append(li);
  });
  jobListDetails.append(jobSummary, jobUl);
  content.append(jobListDetails);

  card.append(header, content);
  container.replaceChildren(card);
}

// -------------------------------------------------------------
// 7. Interactive Event Listeners
// -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  // Track switching
  const tabs = document.getElementById('track-tabs');
  if (tabs) {
    tabs.addEventListener('click', e => {
      const btn = e.target.closest('.track-btn');
      if (!btn) return;
      tabs.querySelectorAll('.track-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.currentTrack = btn.dataset.track;
      loadDashboardData(state.currentTrack);
    });
  }

  // Quick skill search highlight
  const searchInput = document.getElementById('search-skill-input');
  if (searchInput) {
    searchInput.addEventListener('input', e => {
      const term = e.target.value.trim().toLowerCase();
      document.querySelectorAll('.skill-pill').forEach(pill => {
        if (!term) {
          pill.style.background = '#f1f5f9';
          pill.style.borderColor = '#cbd5e1';
          pill.style.color = '#1e40af';
          return;
        }
        if (pill.textContent.toLowerCase().includes(term)) {
          pill.style.background = '#2563eb';
          pill.style.borderColor = '#1d4ed8';
          pill.style.color = '#ffffff';
        } else {
          pill.style.background = '#f1f5f9';
          pill.style.borderColor = '#cbd5e1';
          pill.style.color = '#1e40af';
        }
      });
    });
  }

  // Window resize for ECharts responsiveness
  window.addEventListener('resize', () => {
    if (state.roleChart) state.roleChart.resize();
    if (state.levelChart) state.levelChart.resize();
    if (state.heatmapChart) state.heatmapChart.resize();
  });

  // Initial load
  loadDashboardData('all');
});
