'use strict';

const CATEGORIES = ['unknown','pc','laptop','phone','tablet','router','nas','printer','iot','tv','camera','other'];

// ── Sort state ─────────────────────────────────────────────────────────────
let _devices = [];
let _sortCol = 'last_seen';
let _sortDir = -1;  // -1 = desc, 1 = asc

function sortValue(d, col) {
  switch (col) {
    case 'online':      return d.online ? 1 : 0;
    case 'name':        return (d.name || d.hostname || d.mac).toLowerCase();
    case 'ip':          return (d.ip || '').split('.').map(n => n.padStart(3,'0')).join('.');
    case 'first_seen':
    case 'last_seen':   return d[col] || '';
    case 'notify_online': return d.notify_online ? 1 : 0;
    default:            return (d[col] || '').toString().toLowerCase();
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
    if (th.dataset.col === _sortCol) {
      th.classList.add(_sortDir === 1 ? 'sort-asc' : 'sort-desc');
    }
  });
}

// ── Tab switching ──────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('panel-' + btn.dataset.tab).classList.add('active');
  });
});

// ── Column header click ────────────────────────────────────────────────────
document.querySelectorAll('#panel-devices thead th[data-col]').forEach(th => {
  th.addEventListener('click', () => {
    if (_sortCol === th.dataset.col) {
      _sortDir *= -1;
    } else {
      _sortCol = th.dataset.col;
      _sortDir = 1;
    }
    applySort();
    updateSortHeaders();
    const tbody = document.getElementById('devices-tbody');
    tbody.innerHTML = _devices.map(d => renderDevice(d)).join('');
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
    document.getElementById('device-count').textContent =
      `${_devices.length} devices · ${online} online`;

    if (_devices.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" class="empty">No devices discovered yet. Click Scan Now.</td></tr>';
      return;
    }

    applySort();
    updateSortHeaders();
    tbody.innerHTML = _devices.map(d => renderDevice(d)).join('');
    attachDeviceHandlers();
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="9" class="empty">Failed to load devices.</td></tr>';
  }
}

function renderDevice(d) {
  const dotClass = d.online ? 'dot-online' : 'dot-offline';
  const catOptions = CATEGORIES.map(c =>
    `<option value="${c}" ${c === d.category ? 'selected' : ''}>${c}</option>`
  ).join('');
  const knownClass = d.known ? 'active' : '';
  return `
  <tr data-mac="${d.mac}">
    <td><span class="dot ${dotClass}"></span>${d.online ? 'online' : 'offline'}</td>
    <td>
      <div class="name-cell">
        <button class="known-toggle ${knownClass}" title="Mark as known" data-mac="${d.mac}" data-known="${d.known}">★</button>
        <input class="name-input" data-mac="${d.mac}" value="${escHtml(d.name || d.hostname || '')}" placeholder="${escHtml(d.hostname || d.mac)}" />
      </div>
    </td>
    <td class="mac-text">${d.mac}</td>
    <td class="ip-text">${d.ip || '—'}</td>
    <td>${escHtml(d.vendor || '—')}</td>
    <td><select class="cat-select" data-mac="${d.mac}">${catOptions}</select></td>
    <td>${fmtDate(d.first_seen)}</td>
    <td>${fmtDate(d.last_seen)}</td>
    <td>
      <label title="Alert on power-up"><input type="checkbox" class="chk-online" data-mac="${d.mac}" ${d.notify_online ? 'checked' : ''}> up</label>
      <label title="Alert on power-down" style="margin-left:8px"><input type="checkbox" class="chk-offline" data-mac="${d.mac}" ${d.notify_offline ? 'checked' : ''}> down</label>
    </td>
  </tr>`;
}

function attachDeviceHandlers() {
  // Category change
  document.querySelectorAll('.cat-select').forEach(sel => {
    sel.addEventListener('change', () => patchDevice(sel.dataset.mac, { category: sel.value }));
  });
  // Name edit (on blur)
  document.querySelectorAll('.name-input').forEach(inp => {
    inp.addEventListener('blur', () => patchDevice(inp.dataset.mac, { name: inp.value }));
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') inp.blur(); });
  });
  // Known toggle
  document.querySelectorAll('.known-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      const newVal = btn.dataset.known !== 'true';
      btn.dataset.known = newVal;
      btn.classList.toggle('active', newVal);
      patchDevice(btn.dataset.mac, { known: newVal });
    });
  });
  // Notify checkboxes
  document.querySelectorAll('.chk-online').forEach(chk => {
    chk.addEventListener('change', () => patchDevice(chk.dataset.mac, { notify_online: chk.checked }));
  });
  document.querySelectorAll('.chk-offline').forEach(chk => {
    chk.addEventListener('change', () => patchDevice(chk.dataset.mac, { notify_offline: chk.checked }));
  });
}

async function patchDevice(mac, update) {
  await fetch(`/api/devices/${encodeURIComponent(mac)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  });
}

// ── Events ─────────────────────────────────────────────────────────────────
let _events = [];
let _evSortCol = 'ts';
let _evSortDir = -1;  // -1 = desc (newest first)

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
    if (th.dataset.colEv === _evSortCol) {
      th.classList.add(_evSortDir === 1 ? 'sort-asc' : 'sort-desc');
    }
  });
}

function renderEvents() {
  const tbody = document.getElementById('events-tbody');
  tbody.innerHTML = _events.map(e => `
    <tr>
      <td>${fmtDate(e.ts)}</td>
      <td class="mac-text">${e.mac}</td>
      <td><span class="badge badge-${e.event_type}">${e.event_type.replace('_',' ')}</span></td>
      <td>${fmtDetail(e.detail)}</td>
    </tr>`).join('');
}

document.querySelectorAll('#panel-events thead th[data-col-ev]').forEach(th => {
  th.addEventListener('click', () => {
    if (_evSortCol === th.dataset.colEv) {
      _evSortDir *= -1;
    } else {
      _evSortCol = th.dataset.colEv;
      _evSortDir = 1;
    }
    applyEvSort();
    updateEvSortHeaders();
    renderEvents();
  });
});

async function loadEvents() {
  const tbody = document.getElementById('events-tbody');
  try {
    const res = await fetch('/api/events?limit=200');
    _events = await res.json();
    if (_events.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" class="empty">No events yet.</td></tr>';
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

// ── Helpers ────────────────────────────────────────────────────────────────
function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso + (iso.endsWith('Z') ? '' : 'Z'));
  return d.toLocaleString();
}

function fmtDetail(json) {
  try {
    const obj = JSON.parse(json || '{}');
    return Object.entries(obj).map(([k,v]) => `${k}: ${v}`).join(', ') || '—';
  } catch { return json || '—'; }
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Auto-refresh ───────────────────────────────────────────────────────────
loadDevices();
loadEvents();
setInterval(() => {
  loadDevices();
  loadEvents();
}, 30_000);

document.getElementById('last-refresh').textContent = 'auto-refresh 30s';
