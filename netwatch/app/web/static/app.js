'use strict';

const CATEGORIES = ['unknown','pc','laptop','phone','tablet','router','nas','printer','iot','tv','streamer','camera','other'];

// ── Tab switching ──────────────────────────────────────────────────────────
function switchToTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'panel-' + name));
}

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => switchToTab(btn.dataset.tab));
});

// ── Cross-tab navigation ───────────────────────────────────────────────────
function goToDevice(mac) {
  switchToTab('devices');
  // Wait one frame for the panel to become visible before scrolling
  requestAnimationFrame(() => {
    const row = document.querySelector(`#devices-tbody tr[data-mac="${mac}"]`);
    if (!row) return;
    row.scrollIntoView({ behavior: 'smooth', block: 'center' });
    row.classList.add('row-highlight');
    setTimeout(() => row.classList.remove('row-highlight'), 2000);
  });
}

function goToEvents(mac) {
  document.getElementById('ev-filter-mac').value = mac;
  _evFilterMac = mac.toLowerCase();
  switchToTab('events');
  renderEvents();
}

// ── Sort state — devices ───────────────────────────────────────────────────
let _devices = [];
let _sortCol = 'last_seen';
let _sortDir = -1;

function sortValue(d, col) {
  switch (col) {
    case 'online':        return d.online ? 1 : 0;
    case 'name':          return (d.name || d.hostname || d.mac).toLowerCase();
    case 'ip':            return (d.ip || '').split('.').map(n => n.padStart(3,'0')).join('.');
    case 'first_seen':
    case 'last_seen':     return d[col] || '';
    case 'notify_online': return d.notify_online ? 1 : 0;
    default:              return (d[col] || '').toString().toLowerCase();
  }
}

function applySort() {
  _devices.sort((a, b) => {
    const av = sortValue(a, _sortCol);
    const bv = sortValue(b, _sortCol);
    if (av < bv) return -_sortDir;
    if (av > bv) return  _sortDir;
    return 0;
  });
}

function updateSortHeaders() {
  document.querySelectorAll('#panel-devices thead th[data-col]').forEach(th => {
    th.classList.remove('sort-asc', 'sort-desc');
    if (th.dataset.col === _sortCol) th.classList.add(_sortDir === 1 ? 'sort-asc' : 'sort-desc');
  });
}

document.querySelectorAll('#panel-devices thead th[data-col]').forEach(th => {
  th.addEventListener('click', () => {
    if (_sortCol === th.dataset.col) { _sortDir *= -1; } else { _sortCol = th.dataset.col; _sortDir = 1; }
    applySort();
    updateSortHeaders();
    document.getElementById('devices-tbody').innerHTML = _devices.map(renderDevice).join('');
    attachDeviceHandlers();
  });
});

// ── Devices ────────────────────────────────────────────────────────────────
async function loadDevices() {
  const tbody = document.getElementById('devices-tbody');
  try {
    const res = await fetch('/api/devices');
    _devices = await res.json();
    const online = _devices.filter(d => d.online).length;
    document.getElementById('device-count').textContent = `${_devices.length} devices · ${online} online`;
    if (_devices.length === 0) {
      tbody.innerHTML = '<tr><td colspan="10" class="empty">No devices discovered yet. Click Scan Now.</td></tr>';
      return;
    }
    applySort();
    updateSortHeaders();
    tbody.innerHTML = _devices.map(renderDevice).join('');
    attachDeviceHandlers();
  } catch {
    tbody.innerHTML = '<tr><td colspan="9" class="empty">Failed to load devices.</td></tr>';
  }
}

function renderDevice(d) {
  const dotClass = d.online ? 'dot-online' : 'dot-offline';
  const catOptions = CATEGORIES.map(c =>
    `<option value="${c}" ${c === d.category ? 'selected' : ''}>${c}</option>`
  ).join('');
  const knownClass = d.known ? 'active' : '';
  const ipCell = d.ip
    ? `<button class="ip-link" title="Ping ${d.ip}" data-ip="${d.ip}">${d.ip}</button>`
    : '—';
  return `
  <tr data-mac="${d.mac}">
    <td><span class="dot ${dotClass}"></span>${d.online ? 'online' : 'offline'}</td>
    <td>
      <div class="name-cell">
        <button class="known-toggle ${knownClass}" title="Mark as known" data-mac="${d.mac}" data-known="${d.known}">★</button>
        <input class="name-input" data-mac="${d.mac}" value="${escHtml(d.name || d.hostname || '')}" placeholder="${escHtml(d.hostname || d.mac)}" />
      </div>
    </td>
    <td><button class="mac-link" title="Show events for this device" data-mac="${d.mac}">${d.mac}</button></td>
    <td class="ip-text">${ipCell}</td>
    <td>${escHtml(d.vendor || '—')}</td>
    <td><select class="cat-select" data-mac="${d.mac}">${catOptions}</select></td>
    <td>${fmtDate(d.first_seen)}</td>
    <td>${fmtDate(d.last_seen)}</td>
    <td>
      <label title="Alert on power-up"><input type="checkbox" class="chk-online" data-mac="${d.mac}" ${d.notify_online ? 'checked' : ''}> up</label>
      <label title="Alert on power-down" style="margin-left:8px"><input type="checkbox" class="chk-offline" data-mac="${d.mac}" ${d.notify_offline ? 'checked' : ''}> down</label>
    </td>
    <td class="note-cell"><input class="note-input" data-mac="${d.mac}" maxlength="40" value="${escHtml(d.note || '')}" placeholder="…" /></td>
  </tr>`;
}

function attachDeviceHandlers() {
  document.querySelectorAll('.cat-select').forEach(sel => {
    sel.addEventListener('change', () => patchDevice(sel.dataset.mac, { category: sel.value }));
  });
  document.querySelectorAll('.name-input').forEach(inp => {
    inp.addEventListener('blur', () => patchDevice(inp.dataset.mac, { name: inp.value }));
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') inp.blur(); });
  });
  document.querySelectorAll('.known-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      const newVal = btn.dataset.known !== 'true';
      btn.dataset.known = newVal;
      btn.classList.toggle('active', newVal);
      patchDevice(btn.dataset.mac, { known: newVal });
    });
  });
  document.querySelectorAll('.chk-online').forEach(chk => {
    chk.addEventListener('change', () => patchDevice(chk.dataset.mac, { notify_online: chk.checked }));
  });
  document.querySelectorAll('.chk-offline').forEach(chk => {
    chk.addEventListener('change', () => patchDevice(chk.dataset.mac, { notify_offline: chk.checked }));
  });
  // Note field
  document.querySelectorAll('.note-input').forEach(inp => {
    inp.addEventListener('blur', () => patchDevice(inp.dataset.mac, { note: inp.value }));
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') inp.blur(); });
  });
  // MAC → events cross-link
  document.querySelectorAll('#devices-tbody .mac-link').forEach(btn => {
    btn.addEventListener('click', () => goToEvents(btn.dataset.mac));
  });
  // IP → ping
  document.querySelectorAll('#devices-tbody .ip-link').forEach(btn => {
    btn.addEventListener('click', () => pingIp(btn.dataset.ip, btn));
  });
}

async function patchDevice(mac, update) {
  await fetch(`/api/devices/${encodeURIComponent(mac)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  });
}

// ── Events — sort + filter state ──────────────────────────────────────────
let _events = [];
let _evSortCol = 'ts';
let _evSortDir = -1;
let _evFilterType = '';
let _evFilterMac  = '';

function filteredEvents() {
  return _events.filter(e => {
    if (_evFilterType && e.event_type !== _evFilterType) return false;
    if (_evFilterMac  && !e.mac.toLowerCase().includes(_evFilterMac)) return false;
    return true;
  });
}

function applyEvSort() {
  _events.sort((a, b) => {
    const av = (a[_evSortCol] || '').toString().toLowerCase();
    const bv = (b[_evSortCol] || '').toString().toLowerCase();
    if (av < bv) return -_evSortDir;
    if (av > bv) return  _evSortDir;
    return 0;
  });
}

function updateEvSortHeaders() {
  document.querySelectorAll('#panel-events thead th[data-col-ev]').forEach(th => {
    th.classList.remove('sort-asc', 'sort-desc');
    if (th.dataset.colEv === _evSortCol) th.classList.add(_evSortDir === 1 ? 'sort-asc' : 'sort-desc');
  });
}

function renderEvents() {
  const tbody = document.getElementById('events-tbody');
  const visible = filteredEvents();
  const total = _events.length;
  document.getElementById('ev-filter-count').textContent =
    (visible.length < total) ? `${visible.length} of ${total}` : `${total}`;

  if (visible.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty">No matching events.</td></tr>';
    return;
  }
  tbody.innerHTML = visible.map(e => `
    <tr>
      <td>${fmtDate(e.ts)}</td>
      <td><button class="mac-link" title="Go to device" data-mac="${e.mac}">${e.mac}</button></td>
      <td><span class="badge badge-${e.event_type}">${e.event_type.replace(/_/g,' ')}</span></td>
      <td>${fmtDetail(e.detail)}</td>
    </tr>`).join('');

  // MAC → device cross-link
  tbody.querySelectorAll('.mac-link').forEach(btn => {
    btn.addEventListener('click', () => goToDevice(btn.dataset.mac));
  });
  // IP ping links in detail column
  tbody.querySelectorAll('.ev-ip-link').forEach(btn => {
    btn.addEventListener('click', () => pingIp(btn.dataset.ip, btn));
  });
}

document.querySelectorAll('#panel-events thead th[data-col-ev]').forEach(th => {
  th.addEventListener('click', () => {
    if (_evSortCol === th.dataset.colEv) { _evSortDir *= -1; } else { _evSortCol = th.dataset.colEv; _evSortDir = 1; }
    applyEvSort();
    updateEvSortHeaders();
    renderEvents();
  });
});

// ── Event filters ──────────────────────────────────────────────────────────
document.getElementById('ev-filter-type').addEventListener('change', e => {
  _evFilterType = e.target.value;
  renderEvents();
});

document.getElementById('ev-filter-mac').addEventListener('input', e => {
  _evFilterMac = e.target.value.toLowerCase().trim();
  renderEvents();
});

document.getElementById('ev-filter-clear').addEventListener('click', () => {
  _evFilterType = '';
  _evFilterMac  = '';
  document.getElementById('ev-filter-type').value = '';
  document.getElementById('ev-filter-mac').value  = '';
  renderEvents();
});

async function loadEvents() {
  const tbody = document.getElementById('events-tbody');
  try {
    const res = await fetch('/api/events?limit=200');
    _events = await res.json();
    if (_events.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" class="empty">No events yet.</td></tr>';
      document.getElementById('ev-filter-count').textContent = '0';
      return;
    }
    applyEvSort();
    updateEvSortHeaders();
    renderEvents();
  } catch {
    tbody.innerHTML = '<tr><td colspan="4" class="empty">Failed to load events.</td></tr>';
  }
}

// ── Manual scan ────────────────────────────────────────────────────────────
document.getElementById('scan-btn').addEventListener('click', async () => {
  const btn = document.getElementById('scan-btn');
  btn.innerHTML = '<span class="spinner"></span> Scanning…';
  btn.disabled = true;
  try {
    const res = await fetch('/api/scan', { method: 'POST' });
    const data = await res.json();
    btn.textContent = `Scan Now (${data.found} found)`;
    await loadDevices();
    await loadEvents();
  } catch {
    btn.textContent = 'Scan failed';
  } finally {
    btn.disabled = false;
    setTimeout(() => { btn.textContent = 'Scan Now'; }, 4000);
  }
});

// ── Check status ───────────────────────────────────────────────────────────
document.getElementById('check-btn').addEventListener('click', async () => {
  const btn = document.getElementById('check-btn');
  btn.innerHTML = '<span class="spinner"></span> Checking…';
  btn.disabled = true;
  try {
    const res = await fetch('/api/check-status', { method: 'POST' });
    const data = await res.json();
    const msg = `↑${data.went_online} ↓${data.went_offline} / ${data.checked}`;
    btn.textContent = `Check Status (${msg})`;
    await loadDevices();
    await loadEvents();
  } catch {
    btn.textContent = 'Check failed';
  } finally {
    btn.disabled = false;
    setTimeout(() => { btn.textContent = 'Check Status'; }, 5000);
  }
});

// ── Ping ───────────────────────────────────────────────────────────────────
const IP_RE = /^(\d{1,3}\.){3}\d{1,3}$/;

async function pingIp(ip, btn) {
  const orig = btn.textContent;
  btn.disabled = true;
  btn.textContent = '…';
  try {
    const res = await fetch(`/api/ping/${encodeURIComponent(ip)}`, { method: 'POST' });
    const data = await res.json();
    btn.textContent = orig;
    btn.classList.add(data.online ? 'ping-up' : 'ping-down');
    btn.title = data.online ? `${ip} is UP` : `${ip} is DOWN`;
    setTimeout(() => btn.classList.remove('ping-up', 'ping-down'), 3000);
    // Refresh the device row if it's in our table
    if (data.mac) {
      const idx = _devices.findIndex(d => d.mac === data.mac);
      if (idx !== -1) {
        _devices[idx].online = data.online;
        if (data.online) _devices[idx].last_seen = new Date().toISOString();
        const tbody = document.getElementById('devices-tbody');
        tbody.innerHTML = _devices.map(renderDevice).join('');
        attachDeviceHandlers();
      }
    }
  } catch {
    btn.textContent = orig;
  } finally {
    btn.disabled = false;
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────
function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso + (iso.endsWith('Z') ? '' : 'Z'));
  return d.toLocaleString();
}

function fmtDetail(json) {
  try {
    const obj = JSON.parse(json || '{}');
    return Object.entries(obj).map(([k, v]) => {
      const val = IP_RE.test(String(v))
        ? `<button class="ip-link ev-ip-link" data-ip="${v}" title="Ping ${v}">${v}</button>`
        : escHtml(String(v));
      return `${escHtml(k)}: ${val}`;
    }).join(', ') || '—';
  } catch { return json || '—'; }
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Auto-refresh ───────────────────────────────────────────────────────────
loadDevices();
loadEvents();
setInterval(() => { loadDevices(); loadEvents(); }, 30_000);
document.getElementById('last-refresh').textContent = 'auto-refresh 30s';
