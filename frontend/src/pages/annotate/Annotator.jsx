import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { apiGet, apiPost, apiUrl } from '../../services/api';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CLASS_COLORS = [
  '#ef4444',
  '#3b82f6',
  '#22c55e',
  '#f59e0b',
  '#8b5cf6',
  '#ec4899',
  '#06b6d4',
  '#84cc16',
  '#f97316',
  '#6366f1',
];

const MAX_CANVAS_W = 800;
const MAX_CANVAS_H = 600;

// ---------------------------------------------------------------------------
// Small API helpers for methods not yet in api.ts
// ---------------------------------------------------------------------------

async function apiPut(path, body) {
  const res = await fetch(apiUrl(path), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail;
    try {
      detail = await res.json();
    } catch {
      detail = undefined;
    }
    throw new Error(detail?.detail || `Request failed with ${res.status}`);
  }
  return res.json();
}

async function apiDelete(path) {
  const res = await fetch(apiUrl(path), { method: 'DELETE' });
  if (!res.ok) {
    let detail;
    try {
      detail = await res.json();
    } catch {
      detail = undefined;
    }
    throw new Error(detail?.detail || `Request failed with ${res.status}`);
  }
  // DELETE may return 204 No Content
  if (res.status === 204) return null;
  return res.json();
}

// ---------------------------------------------------------------------------
// Utility: color for a class name given a class list
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

  // --- Core state ---
  const [asset, setAsset] = useState(null);
  const [annotations, setAnnotations] = useState([]);
  const [classes, setClasses] = useState(['object']);
  const [selectedClass, setSelectedClass] = useState('object');
  const [selectedAnnotationIdx, setSelectedAnnotationIdx] = useState(null);
  const [mode, setMode] = useState('box'); // 'box' | 'classify' | 'select'
  const [dirty, setDirty] = useState(false);
  const [status, setStatus] = useState('Loading…');
  const [newClassName, setNewClassName] = useState('');
  const [imageError, setImageError] = useState(false);

  // Scale: canvas coords = image coords * scaleFactor
  const [scaleFactor, setScaleFactor] = useState(1);

  // Drawing state (kept in a ref to avoid stale-closure issues in mouse handlers)
  const drawingRef = useRef({ active: false, startX: 0, startY: 0, currentX: 0, currentY: 0 });

  // Refs
  const canvasRef = useRef(null);
  const imageRef = useRef(new Image());
  const annotationsRef = useRef(annotations);
  const selectedIdxRef = useRef(selectedAnnotationIdx);
  const scaleRef = useRef(scaleFactor);
  const classesRef = useRef(classes);
  const selectedClassRef = useRef(selectedClass);
  const modeRef = useRef(mode);

  // Keep refs in sync with state (needed for mouse-event closures)
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

    // Draw image
    if (img.complete && img.naturalWidth > 0) {
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    } else {
      ctx.fillStyle = '#1e293b';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#94a3b8';
      ctx.font = '14px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Loading image…', canvas.width / 2, canvas.height / 2);
      ctx.textAlign = 'left';
    }

    // Draw annotations
    anns.forEach((ann, idx) => {
      if (ann.type !== 'box') return;
      const { x, y, w, h } = ann.geometry;
      const color = classColor(ann.class_name, cls);
      const cx = x * sf;
      const cy = y * sf;
      const cw = w * sf;
      const ch = h * sf;

      ctx.strokeStyle = color;
      ctx.lineWidth = idx === selIdx ? 3 : 2;
      ctx.setLineDash([]);
      ctx.strokeRect(cx, cy, cw, ch);

      // Label background
      const label = ann.class_name;
      ctx.font = '11px sans-serif';
      const textW = ctx.measureText(label).width + 6;
      ctx.fillStyle = color;
      ctx.fillRect(cx, cy - 16, textW, 16);
      ctx.fillStyle = '#ffffff';
      ctx.fillText(label, cx + 3, cy - 3);

      // Resize handles for selected annotation
      if (idx === selIdx) {
        const handles = [
          [cx, cy],
          [cx + cw / 2, cy],
          [cx + cw, cy],
          [cx + cw, cy + ch / 2],
          [cx + cw, cy + ch],
          [cx + cw / 2, cy + ch],
          [cx, cy + ch],
          [cx, cy + ch / 2],
        ];
        ctx.fillStyle = '#ffffff';
        ctx.strokeStyle = color;
        ctx.lineWidth = 1;
        handles.forEach(([hx, hy]) => {
          ctx.beginPath();
          ctx.arc(hx, hy, 4, 0, Math.PI * 2);
          ctx.fill();
          ctx.stroke();
        });
      }
    });

    // Draw active drawing preview
    if (drawing.active) {
      const { startX, startY, currentX, currentY } = drawing;
      ctx.strokeStyle = '#00ff00';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.strokeRect(startX, startY, currentX - startX, currentY - startY);
      ctx.setLineDash([]);
    }
  }, []);

  // ---------------------------------------------------------------------------
  // Load asset + annotations on mount / assetId change
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!assetId) {
      setStatus('No asset selected. Navigate from the dataset view.');
      return;
    }

    setStatus('Loading…');
    setAnnotations([]);
    setSelectedAnnotationIdx(null);
    setDirty(false);
    setImageError(false);

    async function load() {
      try {
        const assetData = await apiGet(`/api/assets/${assetId}`);
        setAsset(assetData);

        // Load existing annotations
        try {
          const annsData = await apiGet(`/api/assets/${assetId}/annotations`);
          const loaded = Array.isArray(annsData) ? annsData : (annsData.items ?? []);
          setAnnotations(loaded.map((a) => ({ ...a, isNew: false })));

          // Populate classes from existing annotations
          const existingClasses = loaded.map((a) => a.class_name).filter(Boolean);
          if (existingClasses.length > 0) {
            setClasses((prev) => {
              const merged = Array.from(new Set([...prev, ...existingClasses]));
              return merged;
            });
          }
        } catch {
          // Annotations may not exist yet; that's fine
          setAnnotations([]);
        }

        setStatus('Ready');

        // Load image
        const img = imageRef.current;
        img.crossOrigin = 'anonymous';
        img.onload = () => {
          const canvas = canvasRef.current;
          if (!canvas) return;
          const sf = Math.min(MAX_CANVAS_W / img.naturalWidth, MAX_CANVAS_H / img.naturalHeight, 1);
          canvas.width = Math.round(img.naturalWidth * sf);
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
        setStatus(`Error loading asset: ${err.message}`);
      }
    }

    load();
  }, [assetId, redraw]);

  // Re-draw when annotations or selection changes
  useEffect(() => {
    redraw();
  }, [annotations, selectedAnnotationIdx, scaleFactor, redraw]);

  // ---------------------------------------------------------------------------
  // Mouse handlers
  // ---------------------------------------------------------------------------

  function canvasCoords(e) {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    };
  }

  function hitTestAnnotation(cx, cy) {
    const anns = annotationsRef.current;
    const sf = scaleRef.current;
    // Iterate in reverse so topmost box wins
    for (let i = anns.length - 1; i >= 0; i--) {
      const ann = anns[i];
      if (ann.type !== 'box') continue;
      const { x, y, w, h } = ann.geometry;
      if (cx >= x * sf && cx <= (x + w) * sf && cy >= y * sf && cy <= (y + h) * sf) {
        return i;
      }
    }
    return null;
  }

  function handleMouseDown(e) {
    const { x, y } = canvasCoords(e);
    const currentMode = modeRef.current;

    if (currentMode === 'box') {
      drawingRef.current = { active: true, startX: x, startY: y, currentX: x, currentY: y };
      redraw();
    } else if (currentMode === 'select') {
      const idx = hitTestAnnotation(x, y);
      setSelectedAnnotationIdx(idx);
    }
  }

  function handleMouseMove(e) {
    if (!drawingRef.current.active) return;
    const { x, y } = canvasCoords(e);
    drawingRef.current = { ...drawingRef.current, currentX: x, currentY: y };
    redraw();
  }

  function handleMouseUp(e) {
    if (!drawingRef.current.active) return;
    const { startX, startY, currentX, currentY } = drawingRef.current;
    drawingRef.current = { active: false, startX: 0, startY: 0, currentX: 0, currentY: 0 };

    const sf = scaleRef.current;
    const rawX = Math.min(startX, currentX);
    const rawY = Math.min(startY, currentY);
    const rawW = Math.abs(currentX - startX);
    const rawH = Math.abs(currentY - startY);

    // Convert canvas coords back to image coords
    const imgX = rawX / sf;
    const imgY = rawY / sf;
    const imgW = rawW / sf;
    const imgH = rawH / sf;

    // Minimum size check (10x10 in image coords)
    if (imgW < 10 || imgH < 10) {
      redraw();
      return;
    }

    const chosenClass = selectedClassRef.current;
    const newAnn = {
      id: null,
      type: 'box',
      class_name: chosenClass,
      geometry: { x: imgX, y: imgY, w: imgW, h: imgH },
      isNew: true,
    };

    setAnnotations((prev) => {
      const updated = [...prev, newAnn];
      annotationsRef.current = updated;
      return updated;
    });
    setSelectedAnnotationIdx(annotationsRef.current.length); // will be last index after update
    setDirty(true);
    redraw();
  }

  // ---------------------------------------------------------------------------
  // Keyboard handler
  // ---------------------------------------------------------------------------

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        // Only delete if not typing in an input
        if (e.target.tagName === 'INPUT') return;
        const idx = selectedIdxRef.current;
        if (idx !== null) {
          deleteAnnotation(idx);
        }
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
      // If it has a server id, schedule deletion (fire-and-forget)
      if (ann.id) {
        apiDelete(`/api/annotations/${ann.id}`).catch(() => {});
      }
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

  // ---------------------------------------------------------------------------
  // Classification mode
  // ---------------------------------------------------------------------------

  function applyClassification(className) {
    setAnnotations((prev) => {
      // Remove any existing classification annotation, add new one
      const withoutClassify = prev.filter((a) => a.type !== 'classification');
      const newAnn = {
        id: null,
        type: 'classification',
        class_name: className,
        geometry: { class: className },
        isNew: true,
      };
      const updated = [...withoutClassify, newAnn];
      annotationsRef.current = updated;
      return updated;
    });
    setSelectedClass(className);
    setDirty(true);
    setStatus(`Classification set to "${className}"`);
  }

  // ---------------------------------------------------------------------------
  // Save
  // ---------------------------------------------------------------------------

  async function handleSave() {
    if (!assetId) return;
    setStatus('Saving…');
    try {
      const saved = [];
      for (const ann of annotationsRef.current) {
        if (ann.isNew || !ann.id) {
          // POST new annotation
          const body = {
            asset_id: assetId,
            type: ann.type,
            class_name: ann.class_name,
            geometry: ann.geometry,
          };
          const result = await apiPost('/api/annotations', body);
          saved.push({ ...ann, id: result.id, isNew: false });
        } else {
          // PUT existing annotation
          const body = { class_name: ann.class_name, geometry: ann.geometry };
          await apiPut(`/api/annotations/${ann.id}`, body);
          saved.push({ ...ann, isNew: false });
        }
      }

      // Update asset label_status
      try {
        await apiPut(`/api/assets/${assetId}`, { label_status: 'labeled' });
      } catch {
        // Non-fatal
      }

      setAnnotations(saved);
      annotationsRef.current = saved;
      setDirty(false);
      setStatus('Saved');
    } catch (err) {
      setStatus(`Save failed: ${err.message}`);
    }
  }

  // ---------------------------------------------------------------------------
  // Class management
  // ---------------------------------------------------------------------------

  function addClass() {
    const trimmed = newClassName.trim();
    if (!trimmed || classes.includes(trimmed)) return;
    setClasses((prev) => [...prev, trimmed]);
    setSelectedClass(trimmed);
    setNewClassName('');
  }

  // ---------------------------------------------------------------------------
  // Navigation (prev/next asset — uses numeric offset if asset has dataset context)
  // ---------------------------------------------------------------------------

  function navigateAsset(direction) {
    if (!asset) return;
    if (dirty) {
      if (!window.confirm('You have unsaved changes. Leave anyway?')) return;
    }
    // Try to navigate using dataset_id + offset if available, otherwise rely on
    // the parent component / URL. Here we emit a basic history navigation hint.
    const datasetId = asset.dataset_id;
    if (datasetId) {
      // Navigate to dataset view so user can pick the next asset
      navigate(`/datasets/${datasetId}`);
    } else {
      setStatus(`Navigate ${direction === 1 ? 'next' : 'previous'} asset from the dataset view.`);
    }
  }

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------

  if (!assetId) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-500" data-testid="annotator-container">
        <p>No asset selected. Navigate here from the dataset view.</p>
      </div>
    );
  }

  const classificationAnn = annotations.find((a) => a.type === 'classification');
  const boxAnnotations = annotations.filter((a) => a.type === 'box');

  return (
    <div
      className="flex flex-col h-full bg-slate-900 text-slate-100 select-none"
      data-testid="annotator-container"
      role="application"
      aria-label="Annotator"
    >
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-2 bg-slate-800 border-b border-slate-700 text-sm flex-wrap">
        <button
          onClick={() => setMode('box')}
          className={`px-3 py-1 rounded font-medium ${mode === 'box' ? 'bg-blue-600 text-white' : 'bg-slate-700 hover:bg-slate-600'}`}
          aria-pressed={mode === 'box'}
        >
          Box
        </button>
        <button
          onClick={() => setMode('classify')}
          className={`px-3 py-1 rounded font-medium ${mode === 'classify' ? 'bg-blue-600 text-white' : 'bg-slate-700 hover:bg-slate-600'}`}
          aria-pressed={mode === 'classify'}
        >
          Classify
        </button>
        <button
          onClick={() => setMode('select')}
          className={`px-3 py-1 rounded font-medium ${mode === 'select' ? 'bg-blue-600 text-white' : 'bg-slate-700 hover:bg-slate-600'}`}
          aria-pressed={mode === 'select'}
        >
          Select
        </button>
        <div className="w-px h-5 bg-slate-600 mx-1" />
        <button
          onClick={handleSave}
          disabled={!dirty}
          className={`px-3 py-1 rounded font-medium ${dirty ? 'bg-green-600 hover:bg-green-500 text-white' : 'bg-slate-700 text-slate-500 cursor-not-allowed'}`}
        >
          Save
        </button>
        <div className="w-px h-5 bg-slate-600 mx-1" />
        <button
          onClick={() => navigateAsset(-1)}
          className="px-3 py-1 rounded bg-slate-700 hover:bg-slate-600"
          aria-label="Previous asset"
        >
          ← Prev
        </button>
        <button
          onClick={() => navigateAsset(1)}
          className="px-3 py-1 rounded bg-slate-700 hover:bg-slate-600"
          aria-label="Next asset"
        >
          Next →
        </button>
        <span className="ml-2 text-slate-400">
          Asset: <span data-testid="asset-id" className="text-slate-200 font-mono text-xs">{assetId}</span>
        </span>
        {dirty && <span className="ml-auto text-yellow-400 text-xs">Unsaved changes</span>}
      </div>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden min-h-0">
        {/* Left sidebar — Classes */}
        <div className="w-44 flex-shrink-0 bg-slate-800 border-r border-slate-700 flex flex-col p-2 gap-1 overflow-y-auto">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1">Classes</p>
          {classes.map((cls, i) => (
            <button
              key={cls}
              onClick={() => setSelectedClass(cls)}
              className={`flex items-center gap-2 px-2 py-1 rounded text-sm text-left w-full ${selectedClass === cls ? 'bg-slate-600 text-white' : 'hover:bg-slate-700 text-slate-300'}`}
              aria-pressed={selectedClass === cls}
            >
              <span
                className="inline-block w-3 h-3 rounded-full flex-shrink-0"
                style={{ backgroundColor: CLASS_COLORS[i % CLASS_COLORS.length] }}
              />
              <span className="truncate">{cls}</span>
            </button>
          ))}

          {/* Add class */}
          <div className="mt-2 flex flex-col gap-1">
            <input
              type="text"
              value={newClassName}
              onChange={(e) => setNewClassName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addClass()}
              placeholder="New class…"
              className="w-full px-2 py-1 rounded bg-slate-700 border border-slate-600 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
              aria-label="New class name"
            />
            <button
              onClick={addClass}
              disabled={!newClassName.trim()}
              className="w-full px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 text-xs text-slate-300 disabled:opacity-40"
            >
              + Add class
            </button>
          </div>

          {/* Classification mode: show class buttons prominently */}
          {mode === 'classify' && (
            <div className="mt-3 border-t border-slate-700 pt-2">
              <p className="text-xs text-slate-400 mb-1">Set classification:</p>
              {classes.map((cls, i) => (
                <button
                  key={cls}
                  onClick={() => applyClassification(cls)}
                  className={`flex items-center gap-2 px-2 py-1 rounded text-sm text-left w-full mb-1 font-medium ${classificationAnn?.class_name === cls ? 'ring-2 ring-blue-400 bg-slate-600' : 'bg-slate-700 hover:bg-slate-600'}`}
                  style={{ borderLeft: `3px solid ${CLASS_COLORS[i % CLASS_COLORS.length]}` }}
                >
                  <span className="truncate">{cls}</span>
                </button>
              ))}
              {classificationAnn && (
                <p className="text-xs text-green-400 mt-1">
                  Current: {classificationAnn.class_name}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Canvas area */}
        <div className="flex-1 flex items-center justify-center overflow-auto bg-slate-950 p-2">
          {imageError ? (
            <div className="flex flex-col items-center gap-2 text-slate-400">
              <div className="w-24 h-24 bg-slate-800 rounded flex items-center justify-center text-4xl">?</div>
              <p className="text-sm">Image could not be loaded</p>
              <p className="text-xs font-mono text-slate-500">{assetId}</p>
            </div>
          ) : (
            <canvas
              ref={canvasRef}
              className={`border border-slate-700 ${mode === 'box' ? 'cursor-crosshair' : mode === 'select' ? 'cursor-pointer' : 'cursor-default'}`}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={() => {
                if (drawingRef.current.active) {
                  drawingRef.current = { active: false, startX: 0, startY: 0, currentX: 0, currentY: 0 };
                  redraw();
                }
              }}
              style={{ display: 'block', maxWidth: '100%', maxHeight: '100%' }}
              data-testid="annotation-canvas"
            />
          )}
        </div>

        {/* Right sidebar — Annotation list */}
        <div className="w-52 flex-shrink-0 bg-slate-800 border-l border-slate-700 flex flex-col p-2 gap-1 overflow-y-auto">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1">
            Annotations ({annotations.length})
          </p>

          {annotations.length === 0 && (
            <p className="text-xs text-slate-500 italic">No annotations yet.</p>
          )}

          {annotations.map((ann, idx) => (
            <div
              key={idx}
              onClick={() => {
                if (ann.type === 'box') {
                  setSelectedAnnotationIdx(idx === selectedAnnotationIdx ? null : idx);
                }
              }}
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs cursor-pointer group ${idx === selectedAnnotationIdx ? 'bg-slate-600 ring-1 ring-blue-400' : 'hover:bg-slate-700'}`}
              role="option"
              aria-selected={idx === selectedAnnotationIdx}
            >
              <span
                className="inline-block w-2 h-2 rounded-full flex-shrink-0"
                style={{ backgroundColor: classColor(ann.class_name, classes) }}
              />
              <span className="flex-1 truncate text-slate-300">
                {ann.type === 'classification' ? 'cls' : 'box'}: {ann.class_name}
              </span>
              {/* Class change select for box annotations */}
              {ann.type === 'box' && idx === selectedAnnotationIdx && (
                <select
                  value={ann.class_name}
                  onChange={(e) => setAnnotationClass(idx, e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                  className="text-xs bg-slate-700 border border-slate-500 rounded px-1 py-0 text-slate-200 max-w-[70px]"
                  aria-label="Change class"
                >
                  {classes.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              )}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  deleteAnnotation(idx);
                }}
                className="ml-auto text-slate-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity px-1"
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
      <div className="px-3 py-1 bg-slate-800 border-t border-slate-700 text-xs text-slate-400 flex items-center gap-3">
        <span aria-live="polite" data-testid="status">
          {status}
        </span>
        <span className="ml-auto">
          Mode: <span data-testid="mode" className="text-slate-200">{mode}</span>
        </span>
        {scaleFactor !== 1 && (
          <span>Scale: {Math.round(scaleFactor * 100)}%</span>
        )}
        <span>
          {boxAnnotations.length} box{boxAnnotations.length !== 1 ? 'es' : ''}
          {classificationAnn ? ` · classified: ${classificationAnn.class_name}` : ''}
        </span>
      </div>
    </div>
  );
}
