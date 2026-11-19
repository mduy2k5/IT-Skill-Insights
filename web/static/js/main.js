const PAGE_SIZE = 12;
const elements = {
  form: document.getElementById('search-form'),
  search: document.getElementById('search-input'),
  location: document.getElementById('location-filter'),
  level: document.getElementById('level-filter'),
  workMode: document.getElementById('work-mode-filter'),
  reset: document.getElementById('reset-filters'),
  count: document.getElementById('result-count'),
  loading: document.getElementById('loading-state'),
  error: document.getElementById('error-state'),
  errorMessage: document.getElementById('error-message'),
  empty: document.getElementById('empty-state'),
  grid: document.getElementById('jobs-grid'),
  pagination: document.getElementById('pagination'),
};

const filters = { q: '', location: '', level: '', work_mode: '', page: 1 };

function option(select, value, label) {
  const item = document.createElement('option');
  item.value = value;
  item.textContent = label;
  select.appendChild(item);
}

async function loadFilters() {
  const response = await fetch('/api/filters');
  if (!response.ok) throw new Error('Không tải được bộ lọc.');
  const data = await response.json();
  data.locations.forEach(value => option(elements.location, value, value));
  data.levels.forEach(value => option(elements.level, value, value));
}

function modeLabel(mode) {
  return ({
    onsite: 'Tại văn phòng',
    hybrid: 'Kết hợp',
    remote: 'Từ xa',
    unknown: 'Chưa rõ hình thức',
  })[mode] || 'Chưa rõ hình thức';
}

function statusLabel(status) {
  return ({ active: 'Đang tuyển', expired: 'Đã hết hạn', removed: 'Đã gỡ' })[status] || 'Chưa rõ trạng thái';
}

function formatDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'Asia/Ho_Chi_Minh',
  }).format(date);
}

function appendChip(container, label, className = '') {
  if (!label) return;
  const chip = document.createElement('span');
  chip.className = `chip ${className}`.trim();
  chip.textContent = label;
  container.appendChild(chip);
}

function createJobCard(job) {
  const card = document.createElement('article');
  card.className = 'job-card';

  const top = document.createElement('div');
  top.className = 'job-card-top';
  const company = document.createElement('p');
  company.className = 'company-name';
  company.textContent = job.company_name;
  const status = document.createElement('span');
  status.className = `status-pill ${job.listing_status === 'active' ? 'status-active' : ''}`.trim();
  status.textContent = statusLabel(job.listing_status);
  top.append(company, status);

  const title = document.createElement('a');
  title.className = 'job-title';
  title.href = job.detail_url;
  title.textContent = job.title;

  const chips = document.createElement('div');
  chips.className = 'chip-row';
  const location = [job.province_city, job.district].filter(Boolean).join(', ');
  appendChip(chips, location, 'chip-location');
  appendChip(chips, modeLabel(job.work_mode), '');
  appendChip(chips, job.levels, '');

  const bottom = document.createElement('div');
  bottom.className = 'job-card-bottom';
  const posted = document.createElement('span');
  posted.className = 'posted-date';
  posted.textContent = job.published_at ? `Đăng ${formatDate(job.published_at)}` : 'Chưa rõ ngày đăng';
  const salary = document.createElement('span');
  salary.className = 'salary-text';
  salary.textContent = job.salary || 'Lương chưa công bố';
  const detailLink = document.createElement('a');
  detailLink.className = 'detail-link';
  detailLink.href = job.detail_url;
  detailLink.textContent = 'Xem chi tiết →';
  bottom.append(posted, salary, detailLink);

  card.append(top, title, chips, bottom);
  return card;
}

function renderJobs(jobs) {
  elements.grid.replaceChildren(...jobs.map(createJobCard));
  elements.empty.hidden = jobs.length > 0;
}

function pageButton(label, page, disabled = false, active = false) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = `page-button ${active ? 'active' : ''}`.trim();
  button.textContent = label;
  button.disabled = disabled;
  button.addEventListener('click', () => {
    filters.page = page;
    loadJobs();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
  return button;
}

function renderPagination(page, totalPages) {
  elements.pagination.replaceChildren();
  if (totalPages <= 1) return;
  elements.pagination.append(
    pageButton('← Trước', page - 1, page <= 1),
    pageButton(`${page} / ${totalPages}`, page, true, true),
    pageButton('Sau →', page + 1, page >= totalPages),
  );
}

async function loadJobs() {
  elements.loading.hidden = false;
  elements.error.hidden = true;
  elements.empty.hidden = true;
  elements.grid.replaceChildren();
  elements.pagination.replaceChildren();

  const params = new URLSearchParams({ ...filters, page: String(filters.page), per_page: String(PAGE_SIZE) });
  try {
    const response = await fetch(`/api/jobs?${params}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Không tải được danh sách việc làm.');
    elements.count.textContent = `Tìm thấy ${new Intl.NumberFormat('vi-VN').format(data.total)} việc làm`;
    renderJobs(data.jobs);
    renderPagination(data.page, data.total_pages);
  } catch (error) {
    elements.errorMessage.textContent = error.message || 'Kiểm tra kết nối database rồi tải lại trang.';
    elements.error.hidden = false;
    elements.count.textContent = 'Không tải được danh sách';
  } finally {
    elements.loading.hidden = true;
  }
}

function applyFilters() {
  filters.location = elements.location.value;
  filters.level = elements.level.value;
  filters.work_mode = elements.workMode.value;
  filters.page = 1;
  loadJobs();
}

elements.form.addEventListener('submit', event => {
  event.preventDefault();
  filters.q = elements.search.value.trim();
  filters.page = 1;
  loadJobs();
});

elements.location.addEventListener('change', applyFilters);
elements.level.addEventListener('change', applyFilters);
elements.workMode.addEventListener('change', applyFilters);
elements.reset.addEventListener('click', () => {
  elements.form.reset();
  elements.location.value = '';
  elements.level.value = '';
  elements.workMode.value = '';
  Object.assign(filters, { q: '', location: '', level: '', work_mode: '', page: 1 });
  loadJobs();
});

Promise.all([loadFilters(), loadJobs()]).catch(error => {
  elements.errorMessage.textContent = error.message || 'Không tải được dữ liệu.';
  elements.error.hidden = false;
  elements.loading.hidden = true;
});
