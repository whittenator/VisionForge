import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { apiGet, apiPost, apiUrl } from '../../services/api';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

// Muted HUD palette: no pure neon, no gaming colors
const CLASS_COLORS = [
  'oklch(0.72 0.10 82)',   // amber/olive (accent)
  'oklch(0.60 0.10 155)', // muted green
  'oklch(0.68 0.16 20)',  // brick red
  'oklch(0.72 0.08 230)', // slate blue
  'oklch(0.70 0.10 75)',  // warm amber
  'oklch(0.65 0.10 200)', // teal
  'oklch(0.62 0.10 100)', // yellow-green
  'oklch(0.58 0.12 310)', // muted purple
  'oklch(0.68 0.10 40)',  // orange
  'oklch(0.60 0.08 180)', // cyan
];

const MAX_CANVAS_W = 800;
const MAX_CANVAS_H = 600;

// HUD color tokens as canvas-compatible values
const HUD = {
  base:         'oklch(0.10 0.008 240)',
  surface:      'oklch(0.14 0.008 240)',
  elevated:     'oklch(0.18 0.008 240)',
  inset:        'oklch(0.09 0.008 240)',
  borderSubtle: 'oklch(0.20 0.006 240)',
  borderDefault:'oklch(0.26 0.006 240)',
  textMuted:    'oklch(0.42 0.008 240)',
  textSecondary:'oklch(0.65 0.008 240)',
  textData:     'oklch(0.96 0.003 240)',
  accent:       'oklch(0.72 0.10 82)',
  success:      'oklch(0.60 0.10 155)',
  danger:       'oklch(0.52 0.16 20)',
};

// ---------------------------------------------------------------------------
// Small API helpers
// ---------------------------------------------------------------------------

async function apiPut(path, body) {
  const res = await fetch(apiUrl(path), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail;
    try { detail = await res.json(); } catch { detail = undefined; }
    throw new Error(detail?.detail || `Request failed with ${res.status}`);
  }
  return res.json();
}

async function apiDelete(path) {
  const res = await fetch(apiUrl(path), { method: 'DELETE' });
  if (!res.ok) {
    let detail;
    try { detail = await res.json(); } catch { detail = undefined; }
    throw new Error(detail?.detail || `Request failed with ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

function classColor(className, classes) {
  const idx = classes.indexOf(className);
  return CLASS_COLORS[(idx === -1 ? 0 : idx) % CLASS_COLORS.length];
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function AnnotatorPage() {
  const { assetId } = useParams();
  const navigate = useNavigate();

  const [asset, setAsset] = useState(null);
  const [annotations, setAnnotations] = useState([]);
  const [classes, setClasses] = useState(['object']);
  const [selectedClass, setSelectedClass] = useState('object');
  const [selectedAnnotationIdx, setSelectedAnnotationIdx] = useState(null);
  const [mode, setMode] = useState('box');
  const [dirty, setDirty] = useState(false);
  const [status, setStatus] = useState('Loading…');
  const [newClassName, setNewClassName] = useState('');
  const [imageError, setImageError] = useState(false);
  const [scaleFactor, setScaleFactor] = useState(1);

  const drawingRef = useRef({ active: false, startX: 0, startY: 0, currentX: 0, currentY: 0 });
  const canvasRef = useRef(null);
  const imageRef = useRef(new Image());
  const annotationsRef = useRef(annotations);
  const selectedIdxRef = useRef(selectedAnnotationIdx);
  const scaleRef = useRef(scaleFactor);
  const classesRef = useRef(classes);
  const selectedClassRef = useRef(selectedClass);
  const modeRef = useRef(mode);

  useEffect(() => { annotationsRef.current = annotations; }, [annotations]);
  useEffect(() => { selectedIdxRef.current = selectedAnnotationIdx; }, [selectedAnnotationIdx]);
  useEffect(() => { scaleRef.current = scaleFactor; }, [scaleFactor]);
  useEffect(() => { classesRef.current = classes; }, [classes]);
  useEffect(() => { selectedClassRef.current = selectedClass; }, [selectedClass]);
  useEffect(() => { modeRef.current = mode; }, [mode]);

  // ---------------------------------------------------------------------------
  // Canvas drawing
  // ---------------------------------------------------------------------------

  const redraw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const img = imageRef.current;
    const sf = scaleRef.current;
    const anns = annotationsRef.current;
    const selIdx = selectedIdxRef.current;
    const cls = classesRef.current;
    const drawing = drawingRef.current;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (img.complete && img.naturalWidth > 0) {
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    } else {
      ctx.fillStyle = HUD.inset;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = HUD.textMuted;
      ctx.font = '12px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('Loading image…', canvas.width / 2, canvas.height / 2);
      ctx.textAlign = 'left';
    }

    anns.forEach((ann, idx) => {
      if (ann.type !== 'box') return;
      const { x, y, w, h } = ann.geometry;
      const color = classColor(ann.class_name, cls);
      const cx = x * sf, cy = y * sf, cw = w * sf, ch = h * sf;

      ctx.strokeStyle = color;
      ctx.lineWidth = idx === selIdx ? 2 : 1.5;
      ctx.setLineDash([]);
      ctx.strokeRect(cx, cy, cw, ch);

      // Label
      const label = ann.class_name;
      ctx.font = '10px monospace';
      const textW = ctx.measureText(label).width + 8;
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.9;
      ctx.fillRect(cx, cy - 14, textW, 14);
      ctx.globalAlpha = 1;
      ctx.fillStyle = HUD.base;
      ctx.fillText(label, cx + 4, cy - 3);

      // Selection handles
      if (idx === selIdx) {
        const handles = [
          [cx, cy], [cx + cw / 2, cy], [cx + cw, cy],
          [cx + cw, cy + ch / 2], [cx + cw, cy + ch],
          [cx + cw / 2, cy + ch], [cx, cy + ch], [cx, cy + ch / 2],
        ];
        ctx.fillStyle = HUD.textData;
        ctx.strokeStyle = color;
        ctx.lineWidth = 1;
        handles.forEach(([hx, hy]) => {
          ctx.beginPath();
          ctx.rect(hx - 3, hy - 3, 6, 6);
          ctx.fill();
          ctx.stroke();
        });
      }
    });

    if (drawing.active) {
      const { startX, startY, currentX, currentY } = drawing;
      ctx.strokeStyle = HUD.accent;
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.strokeRect(startX, startY, currentX - startX, currentY - startY);
      ctx.setLineDash([]);
    }
  }, []);

  // ---------------------------------------------------------------------------
  // Load asset
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!assetId) { setStatus('No asset selected.'); return; }
    setStatus('Loading…');
    setAnnotations([]);
    setSelectedAnnotationIdx(null);
    setDirty(false);
    setImageError(false);

    async function load() {
      try {
        const assetData = await apiGet(`/api/assets/${assetId}`);
        setAsset(assetData);
        try {
          const annsData = await apiGet(`/api/assets/${assetId}/annotations`);
          const loaded = Array.isArray(annsData) ? annsData : (annsData.items ?? []);
          setAnnotations(loaded.map((a) => ({ ...a, isNew: false })));
          const existingClasses = loaded.map((a) => a.class_name).filter(Boolean);
          if (existingClasses.length > 0) {
            setClasses((prev) => Array.from(new Set([...prev, ...existingClasses])));
          }
        } catch { setAnnotations([]); }
        setStatus('Ready');
        const img = imageRef.current;
        img.crossOrigin = 'anonymous';
        img.onload = () => {
          const canvas = canvasRef.current;
          if (!canvas) return;
          const sf = Math.min(MAX_CANVAS_W / img.naturalWidth, MAX_CANVAS_H / img.naturalHeight, 1);
          canvas.width  = Math.round(img.naturalWidth * sf);
          canvas.height = Math.round(img.naturalHeight * sf);
          setScaleFactor(sf);
          scaleRef.current = sf;
          redraw();
        };
        img.onerror = () => {
          setImageError(true);
          setStatus('Failed to load image');
          const canvas = canvasRef.current;
          if (!canvas) return;
          canvas.width = MAX_CANVAS_W;
          canvas.height = MAX_CANVAS_H;
          redraw();
        };
        img.src = assetData.uri || apiUrl(`/api/assets/${assetId}/file`);
      } catch (err) {
        setStatus(`Error: ${err.message}`);
      }
    }
    load();
  }, [assetId, redraw]);

  useEffect(() => { redraw(); }, [annotations, selectedAnnotationIdx, scaleFactor, redraw]);

  // ---------------------------------------------------------------------------
  // Mouse handlers
  // ---------------------------------------------------------------------------

  function canvasCoords(e) {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }

  function hitTestAnnotation(cx, cy) {
    const anns = annotationsRef.current;
    const sf = scaleRef.current;
    for (let i = anns.length - 1; i >= 0; i--) {
      const ann = anns[i];
      if (ann.type !== 'box') continue;
      const { x, y, w, h } = ann.geometry;
      if (cx >= x * sf && cx <= (x + w) * sf && cy >= y * sf && cy <= (y + h) * sf) return i;
    }
    return null;
  }

  function handleMouseDown(e) {
    const { x, y } = canvasCoords(e);
    if (modeRef.current === 'box') {
      drawingRef.current = { active: true, startX: x, startY: y, currentX: x, currentY: y };
      redraw();
    } else if (modeRef.current === 'select') {
      setSelectedAnnotationIdx(hitTestAnnotation(x, y));
    }
  }

  function handleMouseMove(e) {
    if (!drawingRef.current.active) return;
    const { x, y } = canvasCoords(e);
    drawingRef.current = { ...drawingRef.current, currentX: x, currentY: y };
    redraw();
  }

  function handleMouseUp() {
    if (!drawingRef.current.active) return;
    const { startX, startY, currentX, currentY } = drawingRef.current;
    drawingRef.current = { active: false, startX: 0, startY: 0, currentX: 0, currentY: 0 };
    const sf = scaleRef.current;
    const rawX = Math.min(startX, currentX), rawY = Math.min(startY, currentY);
    const rawW = Math.abs(currentX - startX), rawH = Math.abs(currentY - startY);
    const imgX = rawX / sf, imgY = rawY / sf, imgW = rawW / sf, imgH = rawH / sf;
    if (imgW < 10 || imgH < 10) { redraw(); return; }
    const newAnn = { id: null, type: 'box', class_name: selectedClassRef.current, geometry: { x: imgX, y: imgY, w: imgW, h: imgH }, isNew: true };
    setAnnotations((prev) => {
      const updated = [...prev, newAnn];
      annotationsRef.current = updated;
      return updated;
    });
    setSelectedAnnotationIdx(annotationsRef.current.length);
    setDirty(true);
    redraw();
  }

  // ---------------------------------------------------------------------------
  // Keyboard
  // ---------------------------------------------------------------------------

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (e.target.tagName === 'INPUT') return;
        const idx = selectedIdxRef.current;
        if (idx !== null) deleteAnnotation(idx);
      } else if (e.key === 'Escape') {
        drawingRef.current = { active: false, startX: 0, startY: 0, currentX: 0, currentY: 0 };
        setSelectedAnnotationIdx(null);
        redraw();
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [redraw]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---------------------------------------------------------------------------
  // Annotation CRUD
  // ---------------------------------------------------------------------------

  function deleteAnnotation(idx) {
    setAnnotations((prev) => {
      const ann = prev[idx];
      if (!ann) return prev;
      if (ann.id) apiDelete(`/api/annotations/${ann.id}`).catch(() => {});
      const updated = prev.filter((_, i) => i !== idx);
      annotationsRef.current = updated;
      return updated;
    });
    setSelectedAnnotationIdx(null);
    setDirty(true);
  }

  function setAnnotationClass(idx, className) {
    setAnnotations((prev) => {
      const updated = prev.map((a, i) => (i === idx ? { ...a, class_name: className, isNew: a.isNew || !a.id } : a));
      annotationsRef.current = updated;
      return updated;
    });
    setDirty(true);
  }

  function applyClassification(className) {
    setAnnotations((prev) => {
      const withoutClassify = prev.filter((a) => a.type !== 'classification');
      const newAnn = { id: null, type: 'classification', class_name: className, geometry: { class: className }, isNew: true };
      const updated = [...withoutClassify, newAnn];
      annotationsRef.current = updated;
      return updated;
    });
    setSelectedClass(className);
    setDirty(true);
    setStatus(`Classification → "${className}"`);
  }

  async function handleSave() {
    if (!assetId) return;
    setStatus('Saving…');
    try {
      const saved = [];
      for (const ann of annotationsRef.current) {
        if (ann.isNew || !ann.id) {
          const result = await apiPost('/api/annotations', { asset_id: assetId, type: ann.type, class_name: ann.class_name, geometry: ann.geometry });
          saved.push({ ...ann, id: result.id, isNew: false });
        } else {
          await apiPut(`/api/annotations/${ann.id}`, { class_name: ann.class_name, geometry: ann.geometry });
          saved.push({ ...ann, isNew: false });
        }
      }
      try { await apiPut(`/api/assets/${assetId}`, { label_status: 'labeled' }); } catch { /* non-fatal */ }
      setAnnotations(saved);
      annotationsRef.current = saved;
      setDirty(false);
      setStatus('Saved');
    } catch (err) {
      setStatus(`Save failed: ${err.message}`);
    }
  }

  function addClass() {
    const trimmed = newClassName.trim();
    if (!trimmed || classes.includes(trimmed)) return;
    setClasses((prev) => [...prev, trimmed]);
    setSelectedClass(trimmed);
    setNewClassName('');
  }

  function navigateAsset(direction) {
    if (!asset) return;
    if (dirty && !window.confirm('You have unsaved changes. Leave anyway?')) return;
    const datasetId = asset.dataset_id;
    if (datasetId) { navigate(`/datasets/${datasetId}`); }
    else { setStatus(`Navigate ${direction === 1 ? 'next' : 'previous'} from the dataset view.`); }
  }

  if (!assetId) {
    return (
      <div className="flex items-center justify-center h-64 text-[var(--hud-text-muted)] font-mono text-sm" data-testid="annotator-container">
        No asset selected. Navigate here from the dataset view.
      </div>
    );
  }

  const classificationAnn = annotations.find((a) => a.type === 'classification');
  const boxAnnotations    = annotations.filter((a) => a.type === 'box');

  // Toolbar button helper
  const toolBtn = (label, active, onClick, ariaLabel, ariaPressed) => (
    <button
      onClick={onClick}
      aria-pressed={ariaPressed !== undefined ? ariaPressed : active}
      aria-label={ariaLabel}
      className={[
        'px-3 h-6 text-[0.6875rem] font-mono tracking-widest border transition-colors',
        active
          ? 'bg-[var(--hud-accent)] text-[oklch(0.10_0.008_240)] border-[var(--hud-accent)]'
          : 'bg-transparent text-[var(--hud-text-secondary)] border-[var(--hud-border-default)] hover:border-[var(--hud-border-accent)] hover:text-[var(--hud-accent)]',
      ].join(' ')}
    >
      {label}
    </button>
  );

  return (
    <div
      className="flex flex-col"
      style={{ height: 'calc(100vh - 90px)', background: 'var(--hud-base)' }}
      data-testid="annotator-container"
      role="application"
      aria-label="Annotator"
    >
      {/* Toolbar */}
      <div
        className="flex items-center gap-1.5 px-3 border-b flex-wrap flex-shrink-0"
        style={{
          height: '36px',
          borderColor: 'var(--hud-border-default)',
          background: 'var(--hud-surface)',
        }}
      >
        {/* Mode tools */}
        {toolBtn('BOX',      mode === 'box',      () => setMode('box'),      'Box mode')}
        {toolBtn('CLASSIFY', mode === 'classify', () => setMode('classify'), 'Classify mode')}
        {toolBtn('SELECT',   mode === 'select',   () => setMode('select'),   'Select mode')}

        <div className="w-px h-4 mx-1" style={{ background: 'var(--hud-border-strong)' }} />

        {/* Save */}
        <button
          onClick={handleSave}
          disabled={!dirty}
          className={[
            'px-3 h-6 text-[0.6875rem] font-mono tracking-widest border transition-colors',
            dirty
              ? 'bg-[var(--hud-success-dim)] text-[var(--hud-success-text)] border-[var(--hud-success)] hover:bg-[var(--hud-success)] hover:text-[oklch(0.10_0.008_240)]'
              : 'opacity-30 border-[var(--hud-border-default)] text-[var(--hud-text-muted)] cursor-not-allowed',
          ].join(' ')}
        >
          SAVE
        </button>

        <div className="w-px h-4 mx-1" style={{ background: 'var(--hud-border-strong)' }} />

        {toolBtn('← PREV', false, () => navigateAsset(-1), 'Previous asset')}
        {toolBtn('NEXT →', false, () => navigateAsset(1),  'Next asset')}

        <span className="ml-2 text-[0.6875rem] font-mono text-[var(--hud-text-muted)]">
          ASSET <span data-testid="asset-id" style={{ color: 'var(--hud-text-data)' }}>{assetId}</span>
        </span>

        {dirty && (
          <span className="ml-auto text-[0.6875rem] font-mono pulse-active" style={{ color: 'var(--hud-warning-text)' }}>
            ● UNSAVED
          </span>
        )}
      </div>

      {/* Content row */}
      <div className="flex flex-1 overflow-hidden min-h-0">
        {/* Left sidebar — Classes */}
        <div
          className="flex-shrink-0 flex flex-col gap-1 p-2 overflow-y-auto border-r"
          style={{ width: '152px', background: 'var(--hud-surface)', borderColor: 'var(--hud-border-default)' }}
        >
          <p className="label-overline mb-1">Classes</p>

          {classes.map((cls, i) => (
            <button
              key={cls}
              onClick={() => setSelectedClass(cls)}
              className="flex items-center gap-2 px-2 py-1 text-[0.75rem] text-left w-full border transition-colors"
              style={{
                borderColor: selectedClass === cls ? CLASS_COLORS[i % CLASS_COLORS.length] : 'var(--hud-border-default)',
                background: selectedClass === cls ? 'var(--hud-elevated)' : 'transparent',
                color: selectedClass === cls ? 'var(--hud-text-primary)' : 'var(--hud-text-muted)',
              }}
              aria-pressed={selectedClass === cls}
            >
              <span
                className="inline-block w-2 h-2 flex-shrink-0"
                style={{ background: CLASS_COLORS[i % CLASS_COLORS.length] }}
              />
              <span className="truncate font-mono text-xs">{cls}</span>
            </button>
          ))}

          {/* Add class */}
          <div className="mt-2 space-y-1">
            <input
              type="text"
              value={newClassName}
              onChange={(e) => setNewClassName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addClass()}
              placeholder="new class…"
              aria-label="New class name"
              className="w-full px-2 py-1 text-xs font-mono border focus:outline-none"
              style={{
                background: 'var(--hud-inset)',
                borderColor: 'var(--hud-border-default)',
                color: 'var(--hud-text-primary)',
              }}
            />
            <button
              onClick={addClass}
              disabled={!newClassName.trim()}
              className="w-full px-2 py-1 text-[0.6875rem] font-mono border transition-colors disabled:opacity-30"
              style={{
                background: 'transparent',
                borderColor: 'var(--hud-border-default)',
                color: 'var(--hud-text-muted)',
              }}
            >
              + ADD CLASS
            </button>
          </div>

          {/* Classification mode */}
          {mode === 'classify' && (
            <div className="mt-3 border-t pt-2" style={{ borderColor: 'var(--hud-border-default)' }}>
              <p className="label-overline mb-1">Set class:</p>
              {classes.map((cls, i) => (
                <button
                  key={cls}
                  onClick={() => applyClassification(cls)}
                  className="flex items-center gap-2 px-2 py-1 text-xs font-mono text-left w-full mb-1 border transition-colors"
                  style={{
                    borderColor: classificationAnn?.class_name === cls ? CLASS_COLORS[i % CLASS_COLORS.length] : 'var(--hud-border-default)',
                    background: classificationAnn?.class_name === cls ? 'var(--hud-elevated)' : 'transparent',
                    color: 'var(--hud-text-secondary)',
                    borderLeft: `2px solid ${CLASS_COLORS[i % CLASS_COLORS.length]}`,
                  }}
                >
                  <span className="truncate">{cls}</span>
                </button>
              ))}
              {classificationAnn && (
                <p className="text-[0.6875rem] font-mono mt-1" style={{ color: 'var(--hud-success-text)' }}>
                  ✓ {classificationAnn.class_name}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Canvas area */}
        <div
          className="flex-1 flex items-center justify-center overflow-auto p-3"
          style={{ background: 'var(--hud-inset)' }}
        >
          {imageError ? (
            <div className="flex flex-col items-center gap-2" style={{ color: 'var(--hud-text-muted)' }}>
              <div
                className="w-24 h-24 flex items-center justify-center text-3xl font-mono border"
                style={{ background: 'var(--hud-surface)', borderColor: 'var(--hud-border-default)' }}
              >
                ?
              </div>
              <p className="text-xs font-mono">Image could not be loaded</p>
              <p className="text-[0.6875rem] font-mono" style={{ color: 'var(--hud-text-muted)' }}>{assetId}</p>
            </div>
          ) : (
            <canvas
              ref={canvasRef}
              className={mode === 'box' ? 'cursor-crosshair' : mode === 'select' ? 'cursor-pointer' : 'cursor-default'}
              style={{
                display: 'block',
                maxWidth: '100%',
                maxHeight: '100%',
                border: `1px solid var(--hud-border-default)`,
              }}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={() => {
                if (drawingRef.current.active) {
                  drawingRef.current = { active: false, startX: 0, startY: 0, currentX: 0, currentY: 0 };
                  redraw();
                }
              }}
              data-testid="annotation-canvas"
            />
          )}
        </div>

        {/* Right sidebar — Annotation list */}
        <div
          className="flex-shrink-0 flex flex-col gap-0.5 p-2 overflow-y-auto border-l"
          style={{ width: '176px', background: 'var(--hud-surface)', borderColor: 'var(--hud-border-default)' }}
        >
          <p className="label-overline mb-1">
            Annotations <span className="text-[var(--hud-accent)]">{annotations.length}</span>
          </p>

          {annotations.length === 0 && (
            <p className="text-[0.6875rem] font-mono" style={{ color: 'var(--hud-text-muted)' }}>
              No annotations yet.
            </p>
          )}

          {annotations.map((ann, idx) => (
            <div
              key={idx}
              onClick={() => { if (ann.type === 'box') setSelectedAnnotationIdx(idx === selectedAnnotationIdx ? null : idx); }}
              className="flex items-center gap-1 px-2 py-1 text-xs cursor-pointer group border transition-colors"
              style={{
                borderColor: idx === selectedAnnotationIdx ? 'var(--hud-accent)' : 'transparent',
                background: idx === selectedAnnotationIdx ? 'var(--hud-elevated)' : 'transparent',
              }}
              role="option"
              aria-selected={idx === selectedAnnotationIdx}
            >
              <span
                className="inline-block w-2 h-2 flex-shrink-0"
                style={{ background: classColor(ann.class_name, classes) }}
              />
              <span className="flex-1 truncate font-mono text-[0.6875rem]" style={{ color: 'var(--hud-text-secondary)' }}>
                {ann.type === 'classification' ? 'CLS' : 'BOX'}: {ann.class_name}
              </span>
              {ann.type === 'box' && idx === selectedAnnotationIdx && (
                <select
                  value={ann.class_name}
                  onChange={(e) => setAnnotationClass(idx, e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                  aria-label="Change class"
                  className="text-[0.6875rem] font-mono max-w-[60px] border focus:outline-none"
                  style={{
                    background: 'var(--hud-inset)',
                    borderColor: 'var(--hud-border-default)',
                    color: 'var(--hud-text-primary)',
                  }}
                >
                  {classes.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              )}
              <button
                onClick={(e) => { e.stopPropagation(); deleteAnnotation(idx); }}
                className="ml-auto text-[0.6875rem] font-mono opacity-0 group-hover:opacity-100 transition-opacity px-1"
                style={{ color: 'var(--hud-danger-text)' }}
                aria-label={`Delete annotation ${idx}`}
                title="Delete"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Status bar */}
      <div
        className="px-3 flex items-center gap-4 border-t flex-shrink-0"
        style={{
          height: '28px',
          background: 'var(--hud-surface)',
          borderColor: 'var(--hud-border-default)',
        }}
      >
        <span
          className="text-[0.6875rem] font-mono"
          aria-live="polite"
          data-testid="status"
          style={{ color: 'var(--hud-text-muted)' }}
        >
          {status}
        </span>
        <span className="ml-auto text-[0.6875rem] font-mono" style={{ color: 'var(--hud-text-muted)' }}>
          MODE <span data-testid="mode" style={{ color: 'var(--hud-text-data)' }}>{mode.toUpperCase()}</span>
        </span>
        {scaleFactor !== 1 && (
          <span className="text-[0.6875rem] font-mono" style={{ color: 'var(--hud-text-muted)' }}>
            SCALE <span style={{ color: 'var(--hud-text-data)' }}>{Math.round(scaleFactor * 100)}%</span>
          </span>
        )}
        <span className="text-[0.6875rem] font-mono" style={{ color: 'var(--hud-text-muted)' }}>
          <span style={{ color: 'var(--hud-text-data)' }}>{boxAnnotations.length}</span> box{boxAnnotations.length !== 1 ? 'es' : ''}
          {classificationAnn && (
            <span className="ml-2" style={{ color: 'var(--hud-success-text)' }}>
              ✓ {classificationAnn.class_name}
            </span>
          )}
        </span>
      </div>
    </div>
  );
}
