// app.js — Sudoku Tutor Web Frontend
'use strict';

// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  mode: 'solve',           // 'solve' | 'input' | 'play' | 'create'

  // Solve mode
  steps: [],
  gridStates: [],
  stepIdx: 0,
  showCandidates: true,
  darkMode: false,
  filterDigit: 0,
  autoPlay: false,
  autoTimer: null,

  // Input / Create mode
  editValues: emptyGrid(),
  editHistory: [],
  editFuture: [],
  editGivens: null,        // set when entering input mode from existing puzzle
  inputConflicts: new Set(), // "r,c" keys of conflicting cells in input/create mode

  // Play mode
  playValues: emptyGrid(),
  playGivens: emptyGrid(),
  playSolution: null,
  playUserCands: [],       // [9][9] Set<number>
  playMarkMode: false,
  playErrors: new Set(),

  // Shared
  selected: null,          // [r, c] or null
  highlight: {},           // "r,c" -> 'place'|'elim'|'pattern'|'house'
  hintStep: -1,            // last hint step shown

  // Config (from /api/config)
  hasAnthropicKey: false,
  hasGenerator: false,
  hasPuzzles: false,

  // Puzzle library cache
  puzzleCache: null,
};

// ── Helpers ───────────────────────────────────────────────────────────────────
function emptyGrid() {
  return Array.from({length: 9}, () => Array(9).fill(0));
}

function cloneGrid(g) {
  return g.map(row => row.slice());
}

function key(r, c) { return `${r},${c}`; }

const TIER_NAMES = ['', 'Beginner', 'Intermediate', 'Advanced', 'Expert', 'Master'];

// ── DOM refs ──────────────────────────────────────────────────────────────────
const svg      = document.getElementById('grid-svg');
const panel    = document.getElementById('panel');
const panelTitle = document.getElementById('panel-title');
const panelTier  = document.getElementById('panel-tier');
const panelBody  = document.getElementById('panel-body');
const tlFill   = document.getElementById('timeline-fill');
const tlLabel  = document.getElementById('timeline-label');
const statusBar = document.getElementById('status-bar');
const modeBadge = document.getElementById('mode-badge');

const btnPrev   = document.getElementById('btn-prev');
const btnNext   = document.getElementById('btn-next');
const btnAuto   = document.getElementById('btn-auto');
const btnReset  = document.getElementById('btn-reset');
const btnCands  = document.getElementById('btn-cands');
const btnDark   = document.getElementById('btn-dark');
const btnHint   = document.getElementById('btn-hint');
const btnPlay   = document.getElementById('btn-play');
const btnInput  = document.getElementById('btn-input');
const btnCreate = document.getElementById('btn-create');
const btnPuzzle = document.getElementById('btn-puzzle');
const btnImgUpload = document.getElementById('btn-img-upload');
const imgInput  = document.getElementById('img-upload-input');
const btnApiKey = document.getElementById('btn-apikey');
const apikeyDialog = document.getElementById('apikey-dialog');
const apikeyInput  = document.getElementById('apikey-input');
const apikeyStatus = document.getElementById('apikey-status');
const btnApiKeySave  = document.getElementById('btn-apikey-save');
const btnApiKeyClear = document.getElementById('btn-apikey-clear');
const apikeyDialogClose = document.getElementById('apikey-dialog-close');

const inputControls = document.getElementById('input-controls');
const playControls  = document.getElementById('play-controls');
const btnInputSolve  = document.getElementById('btn-input-solve');
const btnInputCancel = document.getElementById('btn-input-cancel');
const btnInputClear  = document.getElementById('btn-input-clear');
const btnUndo = document.getElementById('btn-undo');
const btnRedo = document.getElementById('btn-redo');
const btnPlayMark      = document.getElementById('btn-play-mark');
const btnPlayClearMarks = document.getElementById('btn-play-clear-marks');
const btnPlayHint      = document.getElementById('btn-play-hint');
const btnPlayExit      = document.getElementById('btn-play-exit');

const puzzleDialog = document.getElementById('puzzle-dialog');
const puzzleDialogClose = document.getElementById('puzzle-dialog-close');
const puzzleTabs = document.getElementById('puzzle-tabs');
const puzzleList = document.getElementById('puzzle-list');

// ── API calls ─────────────────────────────────────────────────────────────────
async function apiSolve(values) {
  const r = await fetch('/api/solve', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({values}),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function apiValidate(values) {
  const r = await fetch('/api/validate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({values}),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function apiBruteForce(values) {
  const r = await fetch('/api/brute-force', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({values}),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function apiPuzzles() {
  const r = await fetch('/api/puzzles');
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function apiGenerate(tier) {
  const r = await fetch('/api/generate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({tier}),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function apiConfig() {
  const r = await fetch('/api/config');
  if (!r.ok) return {};
  return r.json();
}

// ── Grid rendering ────────────────────────────────────────────────────────────
const CELL = 60;

function getCSSColor(varName) {
  return getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
}

function buildHighlight(step) {
  const h = {};
  if (!step) return h;
  for (const cell of (step.pattern_cells || [])) {
    h[key(cell.r, cell.c)] = 'pattern';
  }
  // house cells
  if (step.house_type && step.house_index >= 0) {
    const cells = houseCell(step.house_type, step.house_index);
    for (const [r, c] of cells) {
      if (!h[key(r, c)]) h[key(r, c)] = 'house';
    }
  }
  for (const e of (step.eliminations || [])) {
    h[key(e.r, e.c)] = 'elim';
  }
  for (const p of (step.placements || [])) {
    h[key(p.r, p.c)] = 'place';
  }
  return h;
}

function houseCell(htype, hidx) {
  const cells = [];
  if (htype === 'row') {
    for (let c = 0; c < 9; c++) cells.push([hidx, c]);
  } else if (htype === 'col') {
    for (let r = 0; r < 9; r++) cells.push([r, hidx]);
  } else if (htype === 'box') {
    const br = Math.floor(hidx / 3) * 3;
    const bc = (hidx % 3) * 3;
    for (let dr = 0; dr < 3; dr++)
      for (let dc = 0; dc < 3; dc++)
        cells.push([br + dr, bc + dc]);
  }
  return cells;
}

function cellBg(r, c, gs, step, conflictSet) {
  const k = key(r, c);

  // Conflict
  if (conflictSet && conflictSet.has(k)) return 'var(--conflict-bg)';

  const hi = state.highlight[k];
  if (hi === 'place') return 'var(--place-bg)';
  if (hi === 'elim')  return 'var(--elim-bg)';
  if (hi === 'pattern') return 'var(--pattern-bg)';
  if (hi === 'house') return 'var(--house-bg)';

  // Selected / peers
  if (state.selected) {
    const [sr, sc] = state.selected;
    if (sr === r && sc === c) return 'var(--selected)';
    if (sr === r || sc === c ||
        (Math.floor(sr/3) === Math.floor(r/3) && Math.floor(sc/3) === Math.floor(c/3))) {
      return 'var(--peer-bg)';
    }
  }

  // Filter
  if (state.filterDigit && gs) {
    const v = gs.values[r][c];
    if (v === state.filterDigit) return 'var(--filter-hi)';
    if (v !== 0 && v !== state.filterDigit) return 'var(--filter-dim)';
  }

  if (gs && gs.givens[r][c]) return 'var(--given-bg)';
  return 'var(--bg)';
}

function renderGrid() {
  // Clear SVG
  while (svg.firstChild) svg.removeChild(svg.lastChild);

  let gs = null;
  let conflictSet = null;

  if (state.mode === 'solve') {
    gs = state.gridStates[state.stepIdx] || null;
  } else if (state.mode === 'input' || state.mode === 'create') {
    // Build fake gs from editValues
    gs = {
      values: state.editValues,
      givens: state.editGivens || emptyGrid(),
      candidates: Array.from({length: 9}, () => Array(9).fill([])),
    };
    conflictSet = state.inputConflicts;
  } else if (state.mode === 'play') {
    gs = {
      values: state.playValues,
      givens: state.playGivens,
      candidates: state.playUserCands.map(row => row.map(s => Array.from(s).sort())),
    };
    conflictSet = state.playErrors;
  }

  const step = (state.mode === 'solve' && state.stepIdx > 0)
    ? state.steps[state.stepIdx - 1] : null;

  const ns = 'http://www.w3.org/2000/svg';

  // Cell backgrounds
  for (let r = 0; r < 9; r++) {
    for (let c = 0; c < 9; c++) {
      const rect = document.createElementNS(ns, 'rect');
      rect.setAttribute('x', c * CELL);
      rect.setAttribute('y', r * CELL);
      rect.setAttribute('width', CELL);
      rect.setAttribute('height', CELL);
      rect.setAttribute('fill', cellBg(r, c, gs, step, conflictSet));
      rect.dataset.r = r;
      rect.dataset.c = c;
      svg.appendChild(rect);
    }
  }

  // Cell content
  if (gs) {
    const showCands = state.showCandidates;
    for (let r = 0; r < 9; r++) {
      for (let c = 0; c < 9; c++) {
        const v = gs.values[r][c];
        const x = c * CELL;
        const y = r * CELL;

        if (v !== 0) {
          // Digit
          let fill = gs.givens[r][c] ? 'var(--given-fg)' : 'var(--solved-fg)';
          if (state.mode === 'play' && !gs.givens[r][c]) fill = 'var(--play-fg)';

          // Check filter dimming
          if (state.filterDigit && v !== state.filterDigit && state.mode === 'solve') {
            fill = 'var(--cand-fg)';
          }

          const t = document.createElementNS(ns, 'text');
          t.setAttribute('x', x + CELL / 2);
          t.setAttribute('y', y + CELL / 2 + 11);
          t.setAttribute('text-anchor', 'middle');
          t.setAttribute('font-size', '28');
          t.setAttribute('font-weight', '700');
          t.setAttribute('fill', fill);
          t.setAttribute('font-family', 'monospace, sans-serif');
          t.textContent = v;
          svg.appendChild(t);

        } else if (showCands) {
          // Candidates
          const cands = gs.candidates[r][c];
          const isElim = state.highlight[key(r, c)] === 'elim';

          for (let d = 1; d <= 9; d++) {
            const dr = Math.floor((d - 1) / 3);
            const dc = (d - 1) % 3;
            const cx2 = x + dc * (CELL / 3) + CELL / 6;
            const cy2 = y + dr * (CELL / 3) + CELL / 6 + 4;

            if (cands.includes(d) || (Array.isArray(cands) && cands.indexOf(d) >= 0)) {
              let fill2 = 'var(--cand-fg)';

              // Highlight eliminated candidates
              if (isElim && step) {
                const found = (step.eliminations || []).some(e => e.r === r && e.c === c && e.d === d);
                if (found) fill2 = 'var(--elim-cand)';
              }

              if (state.filterDigit === d) fill2 = 'var(--timeline-fg)';

              const t = document.createElementNS(ns, 'text');
              t.setAttribute('x', cx2);
              t.setAttribute('y', cy2);
              t.setAttribute('text-anchor', 'middle');
              t.setAttribute('font-size', '11');
              t.setAttribute('fill', fill2);
              t.setAttribute('font-family', 'monospace, sans-serif');
              t.textContent = d;
              svg.appendChild(t);
            }
          }
        }
      }
    }
  }

  // Grid lines
  for (let i = 0; i <= 9; i++) {
    const thick = (i % 3 === 0);
    const line = document.createElementNS(ns, 'line');
    line.setAttribute('x1', i * CELL); line.setAttribute('y1', 0);
    line.setAttribute('x2', i * CELL); line.setAttribute('y2', 540);
    line.setAttribute('stroke', thick ? 'var(--grid-thick)' : 'var(--grid-thin)');
    line.setAttribute('stroke-width', thick ? '2.5' : '1');
    svg.appendChild(line);

    const line2 = document.createElementNS(ns, 'line');
    line2.setAttribute('x1', 0);       line2.setAttribute('y1', i * CELL);
    line2.setAttribute('x2', 540);     line2.setAttribute('y2', i * CELL);
    line2.setAttribute('stroke', thick ? 'var(--grid-thick)' : 'var(--grid-thin)');
    line2.setAttribute('stroke-width', thick ? '2.5' : '1');
    svg.appendChild(line2);
  }

  // Selection cursor in input/create/play mode
  if (state.selected && (state.mode === 'input' || state.mode === 'create' || state.mode === 'play')) {
    const [sr, sc] = state.selected;
    const rect = document.createElementNS(ns, 'rect');
    rect.setAttribute('x', sc * CELL + 1.5);
    rect.setAttribute('y', sr * CELL + 1.5);
    rect.setAttribute('width', CELL - 3);
    rect.setAttribute('height', CELL - 3);
    rect.setAttribute('fill', 'none');
    rect.setAttribute('stroke', 'var(--timeline-fg)');
    rect.setAttribute('stroke-width', '2.5');
    svg.appendChild(rect);
  }
}

// ── Panel rendering ────────────────────────────────────────────────────────────
function renderPanel() {
  // Clear any previously appended sections
  const existing = panel.querySelectorAll('.panel-section, .step-list');
  existing.forEach(el => el.remove());

  if (state.mode === 'input' || state.mode === 'create') {
    panelTitle.textContent = state.mode === 'create' ? 'Create Mode' : 'Input Mode';
    panelTier.textContent = '';
    panelBody.textContent = 'Enter digits 1-9. Use arrows to move. Press SOLVE when done, or CANCEL.';
    return;
  }
  if (state.mode === 'play') {
    panelTitle.textContent = 'Play Mode';
    panelTier.textContent = '';
    const filled = state.playValues.flat().filter(v => v !== 0).length;
    const given = state.playGivens.flat().filter(v => v !== 0).length;
    panelBody.textContent = `Cells filled: ${filled - given} / ${81 - given}`;
    return;
  }

  // Solve mode
  const total = state.steps.length;
  if (total === 0) {
    panelTitle.textContent = 'Ready';
    panelTier.textContent = '';
    panelBody.textContent = 'Load a puzzle to begin.';
    return;
  }

  if (state.stepIdx === 0) {
    panelTitle.textContent = 'Starting position';
    panelTier.textContent = `${total} steps total`;
    panelBody.textContent = 'Press NEXT or Space to advance.';
  } else {
    const step = state.steps[state.stepIdx - 1];
    panelTitle.textContent = step.strategy;
    panelTier.textContent = `Tier ${step.tier} — ${TIER_NAMES[step.tier] || ''}  |  Step ${state.stepIdx} / ${total}`;
    panelBody.textContent = step.explanation;

    if (step.placements && step.placements.length) {
      const placed = step.placements.map(p => `R${p.r+1}C${p.c+1}=${p.d}`).join(', ');
      const div = document.createElement('div');
      div.className = 'panel-section';
      div.innerHTML = `Placed: <span>${placed}</span>`;
      panelBody.insertAdjacentElement('afterend', div);
    }
    if (step.eliminations && step.eliminations.length) {
      const elim = {};
      step.eliminations.forEach(e => {
        const k2 = key(e.r, e.c);
        if (!elim[k2]) elim[k2] = [];
        elim[k2].push(e.d);
      });
      const parts = Object.entries(elim).map(([k2, ds]) => {
        const [r2, c2] = k2.split(',').map(Number);
        return `R${r2+1}C${c2+1} {${ds.sort().join(',')}}`;
      }).join(', ');
      const div = document.createElement('div');
      div.className = 'panel-section';
      div.innerHTML = `Eliminated: <span>${parts}</span>`;
      panelBody.insertAdjacentElement('afterend', div);
    }
  }

  // ── Full step list ────────────────────────────────────────────────────────
  const listWrap = document.createElement('div');
  listWrap.className = 'step-list';
  listWrap.style.cssText = 'margin-top:12px; border-top:1px solid var(--panel-line); padding-top:8px;';

  const header = document.createElement('div');
  header.style.cssText = 'font-size:11px; font-weight:700; color:var(--text-muted); margin-bottom:6px; text-transform:uppercase; letter-spacing:0.05em;';
  header.textContent = 'All Steps';
  listWrap.appendChild(header);

  // Only show steps revealed so far
  const visibleSteps = state.steps.slice(0, state.stepIdx);
  if (visibleSteps.length === 0) return;

  visibleSteps.forEach((step, i) => {
    const idx = i + 1;
    const placements = (step.placements || []).map(p => `R${p.r+1}C${p.c+1}=${p.d}`).join(', ');
    const isCurrent = idx === state.stepIdx;

    const row = document.createElement('div');
    row.style.cssText = `
      display:flex; align-items:baseline; gap:6px;
      padding:3px 5px; border-radius:3px; cursor:pointer; font-size:11px;
      background:${isCurrent ? 'var(--selected)' : 'transparent'};
      font-weight:${isCurrent ? '700' : '400'};
    `;
    row.title = step.explanation;

    const numEl = document.createElement('span');
    numEl.style.cssText = 'color:var(--text-muted); min-width:22px; flex-shrink:0;';
    numEl.textContent = idx + '.';

    const placEl = document.createElement('span');
    placEl.style.cssText = 'color:var(--solved-fg); flex:1;';
    placEl.textContent = placements || '—';

    const stratEl = document.createElement('span');
    stratEl.style.cssText = 'color:var(--strategy-fg); white-space:nowrap; flex-shrink:0;';
    stratEl.textContent = step.strategy;

    row.appendChild(numEl);
    row.appendChild(placEl);
    row.appendChild(stratEl);
    row.addEventListener('click', () => goToStep(idx));
    listWrap.appendChild(row);
  });

  panel.appendChild(listWrap);

  // Scroll the last (current) row into view
  const lastRow = listWrap.lastElementChild;
  if (lastRow && lastRow !== header) {
    lastRow.scrollIntoView({block: 'nearest'});
  }
}

// ── Timeline ──────────────────────────────────────────────────────────────────
function renderTimeline() {
  const total = state.steps.length;
  const pct = total > 0 ? (state.stepIdx / total) * 100 : 0;
  tlFill.style.width = pct + '%';
  tlLabel.textContent = `Step ${state.stepIdx} / ${total}`;
}

// ── Toolbar state ─────────────────────────────────────────────────────────────
function renderToolbar() {
  const inSolve  = state.mode === 'solve';
  const inEdit   = state.mode === 'input' || state.mode === 'create';
  const inPlay   = state.mode === 'play';

  // Show/hide control groups
  inputControls.style.display = inEdit ? 'flex' : 'none';
  playControls.style.display  = inPlay ? 'flex' : 'none';

  // Solve-mode buttons
  btnPrev.disabled = !inSolve || state.stepIdx === 0;
  btnNext.disabled = !inSolve || state.stepIdx >= state.steps.length;
  btnAuto.disabled = !inSolve;
  btnReset.disabled = !inSolve;
  btnHint.disabled = !inSolve;

  btnAuto.classList.toggle('on', state.autoPlay);
  btnCands.classList.toggle('on', state.showCandidates);
  btnDark.classList.toggle('on', state.darkMode);

  btnPlay.classList.toggle('on', inPlay);
  btnInput.classList.toggle('on', state.mode === 'input');
  btnCreate.classList.toggle('on', state.mode === 'create');

  // Play controls
  btnPlayMark.classList.toggle('on', state.playMarkMode);

  // Mode badge
  if (inEdit) {
    modeBadge.textContent = state.mode === 'create' ? 'CREATE' : 'INPUT';
    modeBadge.classList.add('visible');
  } else if (inPlay) {
    modeBadge.textContent = 'PLAY';
    modeBadge.classList.add('visible');
  } else {
    modeBadge.classList.remove('visible');
  }

  // Undo/redo
  btnUndo.disabled = state.editHistory.length === 0;
  btnRedo.disabled = state.editFuture.length === 0;
}

// ── Full render ───────────────────────────────────────────────────────────────
function render() {
  renderGrid();
  renderPanel();
  renderTimeline();
  renderToolbar();
  renderDigitFilter();
}

// ── Digit filter ──────────────────────────────────────────────────────────────
function renderDigitFilter() {
  const row = document.getElementById('digit-filter-row');
  row.innerHTML = '';
  for (let d = 1; d <= 9; d++) {
    const btn = document.createElement('button');
    btn.className = 'digit-filter-btn' + (state.filterDigit === d ? ' active' : '');
    btn.textContent = d;
    btn.title = `Filter digit ${d} (press ${d})`;
    btn.addEventListener('click', () => {
      state.filterDigit = state.filterDigit === d ? 0 : d;
      render();
    });
    row.appendChild(btn);
  }
}

// ── Step navigation ───────────────────────────────────────────────────────────
function goToStep(idx) {
  if (idx < 0) idx = 0;
  if (idx > state.steps.length) idx = state.steps.length;
  state.stepIdx = idx;
  state.highlight = idx > 0 ? buildHighlight(state.steps[idx - 1]) : {};
  render();
}

// ── Load puzzle ───────────────────────────────────────────────────────────────
async function loadPuzzle(values) {
  stopAutoPlay();
  setStatus('Solving…');
  try {
    const result = await apiSolve(values);
    if (result.conflict_cells && result.conflict_cells.length > 0) {
      const cells = result.conflict_cells.map(({r, c}) => `R${r+1}C${c+1}`).join(', ');
      alert(`Puzzle has conflicts — cannot solve.\nConflicting cells: ${cells}`);
      setStatus('Puzzle has conflicts — cannot solve.');
      return;
    }
    state.steps = result.steps;
    state.gridStates = result.grid_states;
    state.stepIdx = 0;
    state.highlight = {};
    state.hintStep = -1;
    state.mode = 'solve';
    const diff = result.difficulty;
    const diffName = TIER_NAMES[diff] || 'Unknown';
    setStatus(`Loaded: ${result.steps.length} steps, difficulty Tier ${diff} (${diffName})${result.stuck ? ', STUCK' : ''}`);
    render();
  } catch (e) {
    setStatus('Error: ' + e.message);
  }
}

// ── Auto-play ─────────────────────────────────────────────────────────────────
function startAutoPlay() {
  if (state.autoPlay) return;
  state.autoPlay = true;
  function tick() {
    if (!state.autoPlay) return;
    if (state.stepIdx < state.steps.length) {
      goToStep(state.stepIdx + 1);
      state.autoTimer = setTimeout(tick, 900);
    } else {
      state.autoPlay = false;
      renderToolbar();
    }
  }
  state.autoTimer = setTimeout(tick, 900);
  renderToolbar();
}

function stopAutoPlay() {
  state.autoPlay = false;
  if (state.autoTimer) clearTimeout(state.autoTimer);
  state.autoTimer = null;
}

function toggleAutoPlay() {
  if (state.autoPlay) stopAutoPlay();
  else startAutoPlay();
  renderToolbar();
}

// ── Input / Create mode ───────────────────────────────────────────────────────
async function validateEditGrid() {
  try {
    const result = await apiValidate(state.editValues);
    state.inputConflicts = new Set((result.conflict_cells || []).map(({r, c}) => key(r, c)));
  } catch (e) {
    state.inputConflicts = new Set();
  }
  render();
}

function enterInputMode(existingValues) {
  stopAutoPlay();
  state.mode = 'input';
  state.editValues = existingValues ? cloneGrid(existingValues) : emptyGrid();
  state.editGivens = emptyGrid();
  state.editHistory = [];
  state.editFuture = [];
  state.inputConflicts = new Set();
  state.selected = [4, 4];
  state.highlight = {};
  render();
  if (existingValues) validateEditGrid();
}

function enterCreateMode() {
  stopAutoPlay();
  state.mode = 'create';
  state.editValues = emptyGrid();
  state.editGivens = emptyGrid();
  state.editHistory = [];
  state.editFuture = [];
  state.inputConflicts = new Set();
  state.selected = [4, 4];
  state.highlight = {};
  render();
}

async function exitInputMode(solve) {
  if (!solve) {
    state.mode = 'solve';
    render();
    return;
  }
  await loadPuzzle(cloneGrid(state.editValues));
}

async function exitCreateMode(action) {
  if (action === 'cancel') {
    state.mode = 'solve';
    render();
    return;
  }
  if (action === 'solve') {
    await loadPuzzle(cloneGrid(state.editValues));
    return;
  }
  if (action === 'play') {
    await enterPlayModeFrom(cloneGrid(state.editValues));
  }
}

function setEditDigit(r, c, d) {
  // Push undo
  state.editHistory.push(cloneGrid(state.editValues));
  state.editFuture = [];
  state.editValues[r][c] = d;
  render();
  validateEditGrid();
}

function undoEdit() {
  if (!state.editHistory.length) return;
  state.editFuture.push(cloneGrid(state.editValues));
  state.editValues = state.editHistory.pop();
  render();
  validateEditGrid();
}

function redoEdit() {
  if (!state.editFuture.length) return;
  state.editHistory.push(cloneGrid(state.editValues));
  state.editValues = state.editFuture.pop();
  render();
  validateEditGrid();
}

// ── Play mode ─────────────────────────────────────────────────────────────────
async function enterPlayModeFrom(values) {
  stopAutoPlay();
  state.mode = 'play';
  state.playGivens = cloneGrid(values);
  state.playValues = cloneGrid(values);
  state.playMarkMode = false;
  state.playErrors = new Set();
  state.selected = null;
  state.highlight = {};
  state.playUserCands = Array.from({length: 9}, () =>
    Array.from({length: 9}, () => new Set())
  );

  // Pre-solve to get solution for hints
  try {
    let solution = null;
    const result = await apiSolve(values);
    if (!result.stuck && result.grid_states.length > 0) {
      solution = result.grid_states[result.grid_states.length - 1].values;
    } else {
      const btResult = await apiBruteForce(values);
      solution = btResult.solution;
    }
    state.playSolution = solution;
  } catch (e) {
    state.playSolution = null;
  }
  render();
  setStatus('Play mode: fill in digits. H for hint, M for mark mode.');
}

function exitPlayMode() {
  state.mode = 'solve';
  state.selected = null;
  render();
  setStatus('');
}

function playFillCell(r, c, d) {
  if (state.playGivens[r][c]) return;
  state.playValues[r][c] = d;
  // Validate
  validatePlayBoard();
  render();
}

function playClearCell(r, c) {
  if (state.playGivens[r][c]) return;
  state.playValues[r][c] = 0;
  state.playUserCands[r][c] = new Set();
  state.playErrors.delete(key(r, c));
  render();
}

function playToggleMark(r, c, d) {
  if (state.playGivens[r][c] || state.playValues[r][c]) return;
  const s = state.playUserCands[r][c];
  if (s.has(d)) s.delete(d); else s.add(d);
  render();
}

function playClearMarks() {
  for (let r = 0; r < 9; r++)
    for (let c = 0; c < 9; c++)
      state.playUserCands[r][c] = new Set();
  render();
}

function validatePlayBoard() {
  state.playErrors = new Set();
  if (!state.playSolution) return;
  for (let r = 0; r < 9; r++)
    for (let c = 0; c < 9; c++) {
      const v = state.playValues[r][c];
      if (v && v !== state.playSolution[r][c])
        state.playErrors.add(key(r, c));
    }
}

function advanceHint() {
  if (state.mode !== 'solve') return;
  const next = state.hintStep + 1;
  if (next >= state.steps.length) {
    setStatus('No more hints!');
    return;
  }
  state.hintStep = next;
  goToStep(next + 1);
  setStatus(`Hint: ${state.steps[next].strategy}`);
}

// ── Image import ──────────────────────────────────────────────────────────────
const flashOverlay = document.getElementById('flash-overlay');
const flashTitle   = document.getElementById('flash-title');
const flashSub     = document.getElementById('flash-sub');

function showFlash(title, sub) {
  flashTitle.textContent = title;
  flashSub.textContent   = sub;
  flashOverlay.style.display = 'flex';
}
function hideFlash() {
  flashOverlay.style.display = 'none';
}

function getLocalApiKey() {
  return localStorage.getItem('anthropic_api_key') || '';
}

function hasApiKey() {
  return state.hasAnthropicKey || !!getLocalApiKey();
}

function updateApiKeyButton() {
  const hasKey = hasApiKey();
  btnApiKey.classList.toggle('on', hasKey);
  btnApiKey.title = hasKey ? 'API key set — click to change' : 'Set Anthropic API key for image import';
}

function showApiKeyDialog() {
  const existing = getLocalApiKey();
  apikeyInput.value = existing;
  apikeyStatus.textContent = state.hasAnthropicKey
    ? 'Server has ANTHROPIC_API_KEY set via environment variable.'
    : existing ? 'Key stored in browser localStorage.' : 'No key set — image import will not work.';
  apikeyDialog.showModal();
  apikeyInput.focus();
  apikeyInput.select();
}

async function handleImageUpload(file) {
  if (!file) return;
  if (!hasApiKey()) {
    showApiKeyDialog();
    return;
  }
  showFlash('Extracting puzzle…', 'Sending image to Claude vision API');
  setStatus('Extracting puzzle from image via Claude…');
  const formData = new FormData();
  formData.append('file', file);
  const localKey = getLocalApiKey();
  const headers = localKey ? {'X-Anthropic-Key': localKey} : {};
  try {
    const r = await fetch('/api/extract-image', {method: 'POST', headers, body: formData});
    const data = await r.json();
    hideFlash();
    if (!r.ok) {
      alert('Image extraction failed:\n' + (data.detail || r.statusText));
      setStatus('Image extraction failed.');
      return;
    }
    enterInputMode(data.values);
    setStatus('Puzzle extracted! Verify and press SOLVE.');
  } catch (e) {
    hideFlash();
    alert('Image extraction error: ' + e.message);
    setStatus('Image extraction error.');
  }
}

// ── Puzzle library ────────────────────────────────────────────────────────────
let currentLibraryTier = 0;

async function showPuzzleLibrary() {
  puzzleDialog.showModal();

  if (!state.puzzleCache) {
    puzzleList.innerHTML = '<p style="color:var(--text-muted)">Loading…</p>';
    try {
      state.puzzleCache = await apiPuzzles();
    } catch (e) {
      puzzleList.innerHTML = `<p style="color:var(--warn)">Failed to load: ${e.message}</p>`;
      return;
    }
  }
  renderLibrary(currentLibraryTier);
}

function renderLibrary(tier) {
  currentLibraryTier = tier;

  // Build tabs
  puzzleTabs.innerHTML = '';
  const tiers = [...new Set((state.puzzleCache || []).map(p => p.tier))].sort();
  for (const t of tiers) {
    const btn = document.createElement('button');
    btn.className = 'tab' + (t === tier ? ' active' : '');
    btn.textContent = `Tier ${t}`;
    btn.addEventListener('click', () => renderLibrary(t));
    puzzleTabs.appendChild(btn);
  }
  // Generate tab
  if (state.hasGenerator) {
    const btn = document.createElement('button');
    btn.className = 'tab' + (tier === -1 ? ' active' : '');
    btn.textContent = 'Generate';
    btn.addEventListener('click', () => renderLibrary(-1));
    puzzleTabs.appendChild(btn);
  }

  if (tier === -1) {
    // Generate UI
    puzzleList.innerHTML = '';
    const tierButtons = [0,1,2,3,4].map(t => {
      const b = document.createElement('button');
      b.className = 'btn';
      b.textContent = `Generate Tier ${t}`;
      b.addEventListener('click', async () => {
        b.disabled = true;
        b.innerHTML = '<span class="spinner"></span> Generating…';
        try {
          const result = await apiGenerate(t);
          puzzleDialog.close();
          await loadPuzzle(result.values);
        } catch (e) {
          setStatus('Generate failed: ' + e.message);
          b.disabled = false;
          b.textContent = `Generate Tier ${t}`;
        }
      });
      return b;
    });
    const wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex;flex-direction:column;gap:8px;';
    tierButtons.forEach(b => wrap.appendChild(b));
    puzzleList.appendChild(wrap);
    return;
  }

  // Show puzzles for this tier
  puzzleList.innerHTML = '';
  const filtered = (state.puzzleCache || []).filter(p => p.tier === tier);
  for (const p of filtered) {
    const card = document.createElement('div');
    card.className = 'puzzle-card';
    card.innerHTML = `<div class="puzzle-card-name">${p.name}</div>
                      <div class="puzzle-card-tier">Tier ${p.tier}</div>`;
    card.addEventListener('click', () => {
      puzzleDialog.close();
      loadPuzzle(p.values);
    });
    puzzleList.appendChild(card);
  }
}

// ── Status bar ─────────────────────────────────────────────────────────────────
function setStatus(msg) {
  statusBar.textContent = msg;
}

// ── Keyboard handling ─────────────────────────────────────────────────────────
function moveSelection(dr, dc) {
  if (!state.selected) { state.selected = [0, 0]; render(); return; }
  let [r, c] = state.selected;
  r = (r + dr + 9) % 9;
  c = (c + dc + 9) % 9;
  state.selected = [r, c];
  render();
}

document.addEventListener('keydown', e => {
  // Global
  if (e.key === 'Escape') {
    if (state.mode === 'input' || state.mode === 'create') {
      exitInputMode(false);
      return;
    }
    if (state.mode === 'play') {
      exitPlayMode();
      return;
    }
    stopAutoPlay();
    renderToolbar();
    return;
  }

  if (state.mode === 'solve') {
    handleSolveKey(e);
  } else if (state.mode === 'input' || state.mode === 'create') {
    handleEditKey(e);
  } else if (state.mode === 'play') {
    handlePlayKey(e);
  }
});

function handleSolveKey(e) {
  if (e.key === ' ' || e.key === 'ArrowRight') {
    e.preventDefault();
    if (state.stepIdx < state.steps.length) goToStep(state.stepIdx + 1);
  } else if (e.key === 'ArrowLeft' || e.key === 'Backspace') {
    e.preventDefault();
    if (state.stepIdx > 0) goToStep(state.stepIdx - 1);
  } else if (e.key === 'a' || e.key === 'A') {
    toggleAutoPlay();
  } else if (e.key === 'c' || e.key === 'C') {
    state.showCandidates = !state.showCandidates;
    render();
  } else if (e.key === 'd' || e.key === 'D') {
    toggleDark();
  } else if (e.key === 'r' || e.key === 'R') {
    goToStep(0);
  } else if (e.key === 'h' || e.key === 'H') {
    advanceHint();
  } else if (e.key === 'p' || e.key === 'P') {
    if (state.gridStates.length > 0) {
      enterPlayModeFrom(state.gridStates[0].values);
    }
  } else if (e.key === 'i' || e.key === 'I') {
    const vals = state.gridStates.length > 0 ? state.gridStates[0].values : null;
    enterInputMode(vals);
  } else if (e.key >= '1' && e.key <= '9') {
    const d = parseInt(e.key);
    state.filterDigit = state.filterDigit === d ? 0 : d;
    renderDigitFilter();
    render();
  } else if (e.key === '0') {
    state.filterDigit = 0;
    renderDigitFilter();
    render();
  }
}

function handleEditKey(e) {
  if (e.ctrlKey || e.metaKey) {
    if (e.key === 'z' || e.key === 'Z') { e.preventDefault(); undoEdit(); return; }
    if (e.key === 'y' || e.key === 'Y') { e.preventDefault(); redoEdit(); return; }
  }
  if (e.key === 'ArrowUp')    { e.preventDefault(); moveSelection(-1, 0); return; }
  if (e.key === 'ArrowDown')  { e.preventDefault(); moveSelection(1, 0); return; }
  if (e.key === 'ArrowLeft')  { e.preventDefault(); moveSelection(0, -1); return; }
  if (e.key === 'ArrowRight') { e.preventDefault(); moveSelection(0, 1); return; }
  if (e.key === 'Tab') {
    e.preventDefault();
    if (e.shiftKey) moveSelection(0, -1); else moveSelection(0, 1);
    return;
  }
  if (e.key === 'Enter') {
    e.preventDefault();
    if (state.mode === 'create') exitCreateMode('solve');
    else exitInputMode(true);
    return;
  }
  if (e.key === 'x' || e.key === 'X') {
    state.editHistory.push(cloneGrid(state.editValues));
    state.editValues = emptyGrid();
    state.editFuture = [];
    state.inputConflicts = new Set();
    render();
    return;
  }
  if (state.selected) {
    const [r, c] = state.selected;
    if (e.key >= '1' && e.key <= '9') {
      setEditDigit(r, c, parseInt(e.key));
      moveSelection(0, 1);
    } else if (e.key === '0' || e.key === 'Delete' || e.key === 'Backspace') {
      setEditDigit(r, c, 0);
    }
  }
}

function handlePlayKey(e) {
  if (e.key === 'ArrowUp')    { e.preventDefault(); moveSelection(-1, 0); return; }
  if (e.key === 'ArrowDown')  { e.preventDefault(); moveSelection(1, 0); return; }
  if (e.key === 'ArrowLeft')  { e.preventDefault(); moveSelection(0, -1); return; }
  if (e.key === 'ArrowRight') { e.preventDefault(); moveSelection(0, 1); return; }
  if (e.key === 'm' || e.key === 'M') {
    state.playMarkMode = !state.playMarkMode;
    renderToolbar();
    return;
  }
  if (e.key === 'k' || e.key === 'K') { playClearMarks(); return; }
  if (e.key === 'h' || e.key === 'H') { playHint(); return; }
  if (e.key === 'c' || e.key === 'C') {
    state.showCandidates = !state.showCandidates;
    render();
    return;
  }
  if (!state.selected) return;
  const [r, c] = state.selected;
  if (e.key >= '1' && e.key <= '9') {
    const d = parseInt(e.key);
    if (state.playMarkMode) playToggleMark(r, c, d);
    else { playFillCell(r, c, d); moveSelection(0, 1); }
  } else if (e.key === '0' || e.key === 'Delete' || e.key === 'Backspace') {
    playClearCell(r, c);
  }
}

function playHint() {
  if (!state.playSolution || !state.selected) return;
  const [r, c] = state.selected;
  if (state.playGivens[r][c]) return;
  const d = state.playSolution[r][c];
  if (d) {
    playFillCell(r, c, d);
    setStatus(`Hint: R${r+1}C${c+1} = ${d}`);
  }
}

// ── SVG click handling ────────────────────────────────────────────────────────
svg.addEventListener('click', e => {
  const target = e.target;
  let r = null, c = null;

  // Find the rect under the click
  const elem = document.elementFromPoint(e.clientX, e.clientY);
  const rect = elem.closest ? elem.closest('[data-r]') : null;
  if (rect && rect.dataset.r !== undefined) {
    r = parseInt(rect.dataset.r);
    c = parseInt(rect.dataset.c);
  } else {
    // Fallback: compute from SVG coordinates
    const svgRect = svg.getBoundingClientRect();
    const svgX = (e.clientX - svgRect.left) * (540 / svgRect.width);
    const svgY = (e.clientY - svgRect.top)  * (540 / svgRect.height);
    r = Math.floor(svgY / CELL);
    c = Math.floor(svgX / CELL);
  }

  if (r === null || r < 0 || r > 8 || c < 0 || c > 8) return;

  if (state.mode === 'solve') {
    // Click toggles selection; if same cell clicked twice, deselect
    if (state.selected && state.selected[0] === r && state.selected[1] === c) {
      state.selected = null;
    } else {
      state.selected = [r, c];
    }
    render();
  } else if (state.mode === 'input' || state.mode === 'create') {
    state.selected = [r, c];
    svg.focus();
    render();
  } else if (state.mode === 'play') {
    state.selected = [r, c];
    svg.focus();
    render();
  }
});

svg.addEventListener('keydown', e => {
  if (state.mode === 'input' || state.mode === 'create') handleEditKey(e);
  else if (state.mode === 'play') handlePlayKey(e);
  else if (state.mode === 'solve') handleSolveKey(e);
});

// ── Timeline click ────────────────────────────────────────────────────────────
document.getElementById('timeline-container').addEventListener('click', e => {
  if (state.mode !== 'solve' || state.steps.length === 0) return;
  const rect = e.currentTarget.getBoundingClientRect();
  const pct = (e.clientX - rect.left) / rect.width;
  const idx = Math.round(pct * state.steps.length);
  goToStep(idx);
});

// ── Dark mode ─────────────────────────────────────────────────────────────────
function toggleDark() {
  state.darkMode = !state.darkMode;
  document.documentElement.setAttribute('data-theme', state.darkMode ? 'dark' : '');
  renderToolbar();
  renderGrid();
}

// ── Toolbar button wiring ─────────────────────────────────────────────────────
btnPrev.addEventListener('click', () => { if (state.stepIdx > 0) goToStep(state.stepIdx - 1); });
btnNext.addEventListener('click', () => { if (state.stepIdx < state.steps.length) goToStep(state.stepIdx + 1); });
btnAuto.addEventListener('click', toggleAutoPlay);
btnReset.addEventListener('click', () => goToStep(0));
btnCands.addEventListener('click', () => { state.showCandidates = !state.showCandidates; render(); });
btnDark.addEventListener('click', toggleDark);
btnHint.addEventListener('click', advanceHint);
btnPlay.addEventListener('click', () => {
  if (state.mode === 'play') { exitPlayMode(); return; }
  if (state.gridStates.length > 0) enterPlayModeFrom(state.gridStates[0].values);
});
btnInput.addEventListener('click', () => {
  if (state.mode === 'input') { exitInputMode(false); return; }
  const vals = state.gridStates.length > 0 ? state.gridStates[0].values : null;
  enterInputMode(vals);
});
btnCreate.addEventListener('click', () => {
  if (state.mode === 'create') { exitCreateMode('cancel'); return; }
  enterCreateMode();
});
btnPuzzle.addEventListener('click', showPuzzleLibrary);

btnInputSolve.addEventListener('click', () => {
  if (state.mode === 'create') exitCreateMode('solve');
  else exitInputMode(true);
});
btnInputCancel.addEventListener('click', () => {
  if (state.mode === 'create') exitCreateMode('cancel');
  else exitInputMode(false);
});
btnInputClear.addEventListener('click', () => {
  state.editHistory.push(cloneGrid(state.editValues));
  state.editValues = emptyGrid();
  state.editFuture = [];
  state.inputConflicts = new Set();
  render();
});
btnUndo.addEventListener('click', undoEdit);
btnRedo.addEventListener('click', redoEdit);

btnPlayMark.addEventListener('click', () => { state.playMarkMode = !state.playMarkMode; renderToolbar(); });
btnPlayClearMarks.addEventListener('click', playClearMarks);
btnPlayHint.addEventListener('click', playHint);
btnPlayExit.addEventListener('click', exitPlayMode);

// ── Image upload ──────────────────────────────────────────────────────────────
btnImgUpload.addEventListener('click', () => imgInput.click());
imgInput.addEventListener('change', e => {
  const file = e.target.files[0];
  if (file) handleImageUpload(file);
  imgInput.value = '';
});

function parsePuzzleText(text) {
  const lines = text.trim().split('\n')
    .map(l => l.replace(/[.\-_]/g, '0').replace(/[^0-9]/g, ''))
    .filter(l => l.length === 9);
  if (lines.length !== 9) return null;
  return lines.map(l => l.split('').map(Number));
}

function handlePasteEvent(e) {
  const items = e.clipboardData && e.clipboardData.items;
  if (!items) return;
  // Image takes priority
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      e.preventDefault();
      const file = item.getAsFile();
      if (file) handleImageUpload(file);
      return;
    }
  }
  // Fall back to text puzzle
  const text = e.clipboardData.getData('text');
  if (text) {
    const values = parsePuzzleText(text);
    if (values) {
      e.preventDefault();
      enterInputMode(values);
      setStatus('Puzzle pasted from text. Verify and press SOLVE.');
    }
  }
}
document.addEventListener('paste', handlePasteEvent);
svg.addEventListener('paste', handlePasteEvent);

document.addEventListener('dragover', e => e.preventDefault());
document.addEventListener('drop', e => {
  e.preventDefault();
  const file = e.dataTransfer.files[0];
  if (file && file.type.startsWith('image/')) handleImageUpload(file);
});

// ── API key dialog ────────────────────────────────────────────────────────────
btnApiKey.addEventListener('click', showApiKeyDialog);
apikeyDialogClose.addEventListener('click', () => apikeyDialog.close());
apikeyDialog.addEventListener('click', e => { if (e.target === apikeyDialog) apikeyDialog.close(); });
btnApiKeySave.addEventListener('click', () => {
  const key = apikeyInput.value.trim();
  if (key) {
    localStorage.setItem('anthropic_api_key', key);
    apikeyStatus.textContent = 'Key saved to browser localStorage.';
    apikeyStatus.style.color = 'var(--ok)';
  } else {
    localStorage.removeItem('anthropic_api_key');
    apikeyStatus.textContent = 'Key cleared.';
    apikeyStatus.style.color = 'var(--text-muted)';
  }
  updateApiKeyButton();
  setTimeout(() => apikeyDialog.close(), 800);
});
btnApiKeyClear.addEventListener('click', () => {
  localStorage.removeItem('anthropic_api_key');
  apikeyInput.value = '';
  apikeyStatus.textContent = 'Key cleared.';
  apikeyStatus.style.color = 'var(--text-muted)';
  updateApiKeyButton();
});
apikeyInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') btnApiKeySave.click();
  if (e.key === 'Escape') apikeyDialog.close();
});

// ── Puzzle dialog ─────────────────────────────────────────────────────────────
puzzleDialogClose.addEventListener('click', () => puzzleDialog.close());
puzzleDialog.addEventListener('click', e => { if (e.target === puzzleDialog) puzzleDialog.close(); });

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
  // Load config
  try {
    const cfg = await apiConfig();
    state.hasAnthropicKey = cfg.has_anthropic_key || false;
    state.hasGenerator    = cfg.has_generator || false;
    state.hasPuzzles      = cfg.has_puzzles || false;
    updateApiKeyButton();
  } catch (e) {
    console.warn('Config fetch failed:', e);
  }

  // Load first puzzle from library
  try {
    const puzzles = await apiPuzzles();
    state.puzzleCache = puzzles;
    if (puzzles.length > 0) {
      await loadPuzzle(puzzles[0].values);
    }
  } catch (e) {
    console.warn('Failed to load initial puzzle:', e);
    render();
  }
}

init();
