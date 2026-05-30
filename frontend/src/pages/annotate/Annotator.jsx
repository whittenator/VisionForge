import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { apiGet, apiPost, apiDelete, apiUrl } from '@/services/api';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CLASS_COLORS = [
  'oklch(0.72 0.10 82)',
  'oklch(0.60 0.10 155)',
  'oklch(0.68 0.16 20)',
  'oklch(0.72 0.08 230)',
  'oklch(0.70 0.10 75)',
  'oklch(0.65 0.10 200)',
  'oklch(0.62 0.10 100)',
  'oklch(0.58 0.12 310)',
  'oklch(0.68 0.10 40)',
  'oklch(0.60 0.08 180)',
];

const MAX_CANVAS_W = 900;
const MAX_CANVAS_H = 700;
const HISTORY_LIMIT = 50;

const HUD = {
  base: 'oklch(0.10 0.008 240)',
  surface: 'oklch(0.14 0.008 240)',
  inset: 'oklch(0.09 0.008 240)',
  textMuted: 'oklch(0.42 0.008 240)',
  textData: 'oklch(0.96 0.003 240)',
  accent: 'oklch(0.72 0.10 82)',
};

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

function classColor(className, classes) {
  const idx = classes.indexOf(className);
  return CLASS_COLORS[(idx === -1 ? 0 : idx) % CLASS_COLORS.length];
}

function deepClone(value) {
  if (typeof structuredClone === 'function') return structuredClone(value);
  return JSON.parse(JSON.stringify(value));
}

function distSq(a, b) {
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  return dx * dx + dy * dy;
}

function pointInPolygon(px, py, points) {
  let inside = false;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const xi = points[i].x;
    const yi = points[i].y;
    const xj = points[j].x;
    const yj = points[j].y;
    const intersect =
      yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi + 1e-9) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
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
  // mode: 'box' | 'polygon' | 'keypoint' | 'classify' | 'select'
  const [mode, setMode] = useState('box');
  const [dirty, setDirty] = useState(false);
  const [status, setStatus] = useState('Loading…');
  const [newClassName, setNewClassName] = useState('');
  const [imageError, setImageError] = useState(false);
  const [scaleFactor, setScaleFactor] = useState(1);
  const [neighbors, setNeighbors] = useState({ prev: null, next: null, index: null, total: 0 });
  const [datasetName, setDatasetName] = useState('');
  const [imgDims, setImgDims] = useState({ w: 0, h: 0 });
  const [showAddClass, setShowAddClass] = useState(false);
  // In-progress polygon: array of points (image coordinates)
  const [polygonInProgress, setPolygonInProgress] = useState([]);

  // Undo/redo stacks. Each entry is a snapshot of the annotations array.
  const undoStack = useRef([]);
  const redoStack = useRef([]);

  const drawingRef = useRef({ active: false, startX: 0, startY: 0, currentX: 0, currentY: 0 });
  const canvasRef = useRef(null);
  const imageRef = useRef(new Image());
  const annotationsRef = useRef(annotations);
  const selectedIdxRef = useRef(selectedAnnotationIdx);
  const scaleRef = useRef(scaleFactor);
  const classesRef = useRef(classes);
  const selectedClassRef = useRef(selectedClass);
  const modeRef = useRef(mode);
  const polygonInProgressRef = useRef(polygonInProgress);

  useEffect(() => {
    annotationsRef.current = annotations;
  }, [annotations]);
  useEffect(() => {
    selectedIdxRef.current = selectedAnnotationIdx;
  }, [selectedAnnotationIdx]);
  useEffect(() => {
    scaleRef.current = scaleFactor;
  }, [scaleFactor]);
  useEffect(() => {
    classesRef.current = classes;
  }, [classes]);
  useEffect(() => {
    selectedClassRef.current = selectedClass;
  }, [selectedClass]);
  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);
  useEffect(() => {
    polygonInProgressRef.current = polygonInProgress;
  }, [polygonInProgress]);

  // -------------------------------------------------------------------------
  // History (undo/redo)
  // -------------------------------------------------------------------------

  function pushHistory() {
    undoStack.current.push(deepClone(annotationsRef.current));
    if (undoStack.current.length > HISTORY_LIMIT) undoStack.current.shift();
    redoStack.current = [];
  }

  function applySnapshot(snapshot) {
    annotationsRef.current = snapshot;
    setAnnotations(snapshot);
    setSelectedAnnotationIdx(null);
    setDirty(true);
  }

  function undo() {
    if (undoStack.current.length === 0) return;
    redoStack.current.push(deepClone(annotationsRef.current));
    const prev = undoStack.current.pop();
    applySnapshot(prev);
    setStatus('Undid');
  }

  function redo() {
    if (redoStack.current.length === 0) return;
    undoStack.current.push(deepClone(annotationsRef.current));
    const next = redoStack.current.pop();
    applySnapshot(next);
    setStatus('Redid');
  }

  // -------------------------------------------------------------------------
  // Canvas drawing
  // -------------------------------------------------------------------------

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
    const polyInProgress = polygonInProgressRef.current;

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
      const color = classColor(ann.class_name, cls);
      const isSel = idx === selIdx;
      ctx.strokeStyle = color;
      ctx.lineWidth = isSel ? 2 : 1.5;
      ctx.setLineDash([]);

      if (ann.type === 'box') {
        const { x, y, w, h } = ann.geometry;
        ctx.strokeRect(x * sf, y * sf, w * sf, h * sf);
        labelTag(ctx, ann.class_name || '', x * sf, y * sf, color);
        if (isSel) drawHandlesForBox(ctx, x * sf, y * sf, w * sf, h * sf, color);
      } else if (ann.type === 'polygon') {
        const pts = ann.geometry.points || [];
        if (pts.length > 1) {
          ctx.beginPath();
          ctx.moveTo(pts[0].x * sf, pts[0].y * sf);
          for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x * sf, pts[i].y * sf);
          ctx.closePath();
          ctx.fillStyle = color;
          ctx.globalAlpha = 0.15;
          ctx.fill();
          ctx.globalAlpha = 1;
          ctx.stroke();
          labelTag(
            ctx,
            ann.class_name || '',
            pts[0].x * sf,
            pts[0].y * sf,
            color
          );
          if (isSel) pts.forEach((p) => drawPointHandle(ctx, p.x * sf, p.y * sf, color));
        }
      } else if (ann.type === 'keypoint') {
        const pts = ann.geometry.points || [];
        pts.forEach((p, i) => {
          drawPointHandle(ctx, p.x * sf, p.y * sf, color, isSel ? 6 : 4);
          if (i === 0)
            labelTag(ctx, ann.class_name || '', p.x * sf - 2, p.y * sf, color);
        });
      }
    });

    // In-progress polygon
    if (modeRef.current === 'polygon' && polyInProgress.length > 0) {
      ctx.strokeStyle = HUD.accent;
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(polyInProgress[0].x * sf, polyInProgress[0].y * sf);
      for (let i = 1; i < polyInProgress.length; i++)
        ctx.lineTo(polyInProgress[i].x * sf, polyInProgress[i].y * sf);
      ctx.stroke();
      ctx.setLineDash([]);
      polyInProgress.forEach((p) =>
        drawPointHandle(ctx, p.x * sf, p.y * sf, HUD.accent, 4)
      );
    }

    // In-progress box drag
    if (drawing.active) {
      const { startX, startY, currentX, currentY } = drawing;
      ctx.strokeStyle = HUD.accent;
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.strokeRect(startX, startY, currentX - startX, currentY - startY);
      ctx.setLineDash([]);
    }
  }, []);

  function labelTag(ctx, label, x, y, color) {
    if (!label) return;
    ctx.font = '10px monospace';
    const w = ctx.measureText(label).width + 8;
    ctx.fillStyle = color;
    ctx.globalAlpha = 0.9;
    ctx.fillRect(x, y - 14, w, 14);
    ctx.globalAlpha = 1;
    ctx.fillStyle = HUD.base;
    ctx.fillText(label, x + 4, y - 3);
  }

  function drawPointHandle(ctx, x, y, color, size = 5) {
    ctx.fillStyle = HUD.textData;
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.rect(x - size / 2, y - size / 2, size, size);
    ctx.fill();
    ctx.stroke();
  }

  function drawHandlesForBox(ctx, cx, cy, cw, ch, color) {
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
    handles.forEach(([hx, hy]) => drawPointHandle(ctx, hx, hy, color, 6));
  }

  // -------------------------------------------------------------------------
  // Load asset + neighbors
  // -------------------------------------------------------------------------

  useEffect(() => {
    if (!assetId) {
      setStatus('No asset selected.');
      return;
    }
    setStatus('Loading…');
    setAnnotations([]);
    setSelectedAnnotationIdx(null);
    setPolygonInProgress([]);
    undoStack.current = [];
    redoStack.current = [];
    setDirty(false);
    setImageError(false);

    async function load() {
      try {
        const assetData = await apiGet(`/api/assets/${assetId}`);
        setAsset(assetData);

        // Pre-populate the class sidebar from the dataset's ClassMap so
        // annotators don't have to re-add classes every session.
        try {
          if (assetData.dataset_id) {
            const dataset = await apiGet(`/api/datasets/${assetData.dataset_id}`);
            if (dataset?.name) setDatasetName(dataset.name);
            const seeded = Array.isArray(dataset.classes) ? dataset.classes : [];
            const names = seeded
              .map((c) => (typeof c === 'string' ? c : c?.name))
              .filter(Boolean);
            if (names.length > 0) {
              setClasses(names);
              setSelectedClass(names[0]);
            }
          }
        } catch {
          // Falls back to the default ['object'] class.
        }

        try {
          const annsData = await apiGet(`/api/assets/${assetId}/annotations`);
          const loaded = Array.isArray(annsData) ? annsData : annsData.items ?? [];
          setAnnotations(loaded.map((a) => ({ ...a, isNew: false, dirty: false })));
          const existingClasses = loaded.map((a) => a.class_name).filter(Boolean);
          if (existingClasses.length > 0) {
            setClasses((prev) => Array.from(new Set([...prev, ...existingClasses])));
          }
        } catch {
          setAnnotations([]);
        }

        try {
          const n = await apiGet(`/api/assets/${assetId}/neighbors`);
          setNeighbors(n);
        } catch {
          setNeighbors({ prev: null, next: null, index: null, total: 0 });
        }

        setStatus('Ready');
        const img = imageRef.current;
        img.crossOrigin = 'anonymous';
        img.onload = () => {
          const canvas = canvasRef.current;
          if (!canvas) return;
          const sf = Math.min(
            MAX_CANVAS_W / img.naturalWidth,
            MAX_CANVAS_H / img.naturalHeight,
            1
          );
          canvas.width = Math.round(img.naturalWidth * sf);
          canvas.height = Math.round(img.naturalHeight * sf);
          setImgDims({ w: img.naturalWidth, h: img.naturalHeight });
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
        img.src =
          assetData.download_url || assetData.uri || apiUrl(`/api/assets/${assetId}/file`);
      } catch (err) {
        setStatus(`Error: ${err.message}`);
      }
    }
    load();
  }, [assetId, redraw]);

  useEffect(() => {
    redraw();
  }, [annotations, selectedAnnotationIdx, scaleFactor, polygonInProgress, redraw]);

  // -------------------------------------------------------------------------
  // Mouse handlers
  // -------------------------------------------------------------------------

  function canvasCoords(e) {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }

  function imageCoords(canvasX, canvasY) {
    const sf = scaleRef.current;
    return { x: canvasX / sf, y: canvasY / sf };
  }

  function hitTestAnnotation(canvasX, canvasY) {
    const anns = annotationsRef.current;
    const sf = scaleRef.current;
    const { x: ix, y: iy } = imageCoords(canvasX, canvasY);
    for (let i = anns.length - 1; i >= 0; i--) {
      const ann = anns[i];
      if (ann.type === 'box') {
        const { x, y, w, h } = ann.geometry;
        if (ix >= x && ix <= x + w && iy >= y && iy <= y + h) return i;
      } else if (ann.type === 'polygon') {
        if (pointInPolygon(ix, iy, ann.geometry.points || [])) return i;
      } else if (ann.type === 'keypoint') {
        const pts = ann.geometry.points || [];
        for (const p of pts) {
          if (Math.sqrt(distSq({ x: p.x * sf, y: p.y * sf }, { x: canvasX, y: canvasY })) < 8)
            return i;
        }
      }
    }
    return null;
  }

  function handleMouseDown(e) {
    const { x, y } = canvasCoords(e);
    const m = modeRef.current;
    if (m === 'box') {
      drawingRef.current = { active: true, startX: x, startY: y, currentX: x, currentY: y };
      redraw();
    } else if (m === 'polygon') {
      const ip = imageCoords(x, y);
      const pts = polygonInProgressRef.current;
      // double-click logic: finalize when clicking near the first point with >=3 pts
      if (
        pts.length >= 3 &&
        Math.sqrt(distSq({ x: pts[0].x * scaleRef.current, y: pts[0].y * scaleRef.current }, { x, y })) < 10
      ) {
        finalizePolygon();
        return;
      }
      const next = [...pts, ip];
      polygonInProgressRef.current = next;
      setPolygonInProgress(next);
      redraw();
    } else if (m === 'keypoint') {
      const ip = imageCoords(x, y);
      pushHistory();
      const newAnn = {
        id: null,
        type: 'keypoint',
        class_name: selectedClassRef.current,
        geometry: { points: [ip] },
        isNew: true,
        dirty: true,
        version: 0,
      };
      let newIdx = 0;
      setAnnotations((prev) => {
        newIdx = prev.length; // index of the appended item in the new array
        const updated = [...prev, newAnn];
        annotationsRef.current = updated;
        return updated;
      });
      setSelectedAnnotationIdx(newIdx);
      setDirty(true);
      redraw();
    } else if (m === 'select') {
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
    const rawX = Math.min(startX, currentX);
    const rawY = Math.min(startY, currentY);
    const rawW = Math.abs(currentX - startX);
    const rawH = Math.abs(currentY - startY);
    const imgX = rawX / sf;
    const imgY = rawY / sf;
    const imgW = rawW / sf;
    const imgH = rawH / sf;
    if (imgW < 5 || imgH < 5) {
      // Treat a non-drag as a click: select whatever box is under the cursor.
      setSelectedAnnotationIdx(hitTestAnnotation(currentX, currentY));
      redraw();
      return;
    }
    pushHistory();
    const newAnn = {
      id: null,
      type: 'box',
      class_name: selectedClassRef.current,
      geometry: { x: imgX, y: imgY, w: imgW, h: imgH },
      isNew: true,
      dirty: true,
      version: 0,
    };
    let newIdx = 0;
    setAnnotations((prev) => {
      newIdx = prev.length;
      const updated = [...prev, newAnn];
      annotationsRef.current = updated;
      return updated;
    });
    setSelectedAnnotationIdx(newIdx);
    setDirty(true);
    redraw();
  }

  function finalizePolygon() {
    const pts = polygonInProgressRef.current;
    if (pts.length < 3) {
      setStatus('Polygon needs at least 3 points');
      return;
    }
    pushHistory();
    const newAnn = {
      id: null,
      type: 'polygon',
      class_name: selectedClassRef.current,
      geometry: { points: pts.slice() },
      isNew: true,
      dirty: true,
      version: 0,
    };
    let newIdx = 0;
    setAnnotations((prev) => {
      newIdx = prev.length;
      const updated = [...prev, newAnn];
      annotationsRef.current = updated;
      return updated;
    });
    polygonInProgressRef.current = [];
    setPolygonInProgress([]);
    setSelectedAnnotationIdx(newIdx);
    setDirty(true);
    setStatus('Polygon finalized');
  }

  // -------------------------------------------------------------------------
  // Keyboard
  // -------------------------------------------------------------------------

  useEffect(() => {
    function onKeyDown(e) {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
        e.preventDefault();
        if (e.shiftKey) redo();
        else undo();
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') {
        e.preventDefault();
        redo();
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        handleSave();
        return;
      }
      if (e.key === 'Delete' || e.key === 'Backspace') {
        const idx = selectedIdxRef.current;
        if (idx !== null) deleteAnnotation(idx);
      } else if (e.key === 'Escape') {
        drawingRef.current = { active: false, startX: 0, startY: 0, currentX: 0, currentY: 0 };
        polygonInProgressRef.current = [];
        setPolygonInProgress([]);
        setSelectedAnnotationIdx(null);
        redraw();
      } else if (e.key === 'Enter' && modeRef.current === 'polygon') {
        finalizePolygon();
      } else if (e.key === 'b' || e.key === 'B') setMode('box');
      else if (e.key === 'p' || e.key === 'P') setMode('polygon');
      else if (e.key === 'k' || e.key === 'K') setMode('keypoint');
      else if (e.key === 'v' || e.key === 'V') setMode('select');
      else if (e.key === 'c' || e.key === 'C') setMode('classify');
      else if (e.key === 'ArrowLeft' && neighbors.prev) navigateAsset(-1);
      else if (e.key === 'ArrowRight' && neighbors.next) navigateAsset(1);
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [neighbors.prev, neighbors.next]);

  // -------------------------------------------------------------------------
  // Annotation CRUD
  // -------------------------------------------------------------------------

  function deleteAnnotation(idx) {
    pushHistory();
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
    pushHistory();
    setAnnotations((prev) => {
      const updated = prev.map((a, i) =>
        i === idx ? { ...a, class_name: className, dirty: true } : a
      );
      annotationsRef.current = updated;
      return updated;
    });
    setDirty(true);
  }

  function applyClassification(className) {
    pushHistory();
    setAnnotations((prev) => {
      const withoutClassify = prev.filter((a) => a.type !== 'classification');
      const newAnn = {
        id: null,
        type: 'classification',
        class_name: className,
        geometry: { class: className },
        isNew: true,
        dirty: true,
        version: 0,
      };
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
      const creates = [];
      const updates = [];
      const current = annotationsRef.current;
      current.forEach((ann, idx) => {
        if (ann.isNew || !ann.id) {
          creates.push({
            client_id: `idx-${idx}`,
            asset_id: assetId,
            type: ann.type,
            geometry: ann.geometry,
            class_name: ann.class_name,
          });
        } else if (ann.dirty) {
          updates.push({
            id: ann.id,
            geometry: ann.geometry,
            class_name: ann.class_name,
            expected_version: ann.version,
          });
        }
      });
      if (creates.length === 0 && updates.length === 0) {
        setDirty(false);
        setStatus('Nothing to save');
        return;
      }
      const result = await apiPost('/api/annotations/bulk', {
        creates,
        updates,
        deletes: [],
      });

      const createdById = new Map();
      (result.created || []).forEach((row) => {
        if (row.client_id && row.status === 'ok' && row.annotation) {
          createdById.set(row.client_id, row.annotation);
        }
      });
      const updatedById = new Map();
      (result.updated || []).forEach((row) => {
        if (row.id) updatedById.set(row.id, row);
      });

      const next = current.map((ann, idx) => {
        if (ann.isNew || !ann.id) {
          const created = createdById.get(`idx-${idx}`);
          if (created) {
            return {
              ...ann,
              id: created.id,
              version: created.version,
              isNew: false,
              dirty: false,
            };
          }
          return ann;
        }
        if (ann.dirty) {
          const u = updatedById.get(ann.id);
          if (!u) return ann;
          if (u.status === 'ok' && u.annotation) {
            return { ...ann, version: u.annotation.version, dirty: false };
          }
          if (u.status === 'conflict') {
            setStatus(`Conflict on ${ann.id}: another editor changed it`);
            return ann;
          }
        }
        return ann;
      });

      setAnnotations(next);
      annotationsRef.current = next;
      const errors = [
        ...(result.created || []).filter((r) => r.status !== 'ok'),
        ...(result.updated || []).filter((r) => r.status !== 'ok'),
      ];
      if (errors.length === 0) {
        setDirty(false);
        setStatus('Saved');
      } else {
        setDirty(true);
        setStatus(`Saved with ${errors.length} issue(s) — see status`);
      }
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
    if (dirty && !window.confirm('You have unsaved changes. Leave anyway?')) return;
    const target = direction === 1 ? neighbors.next : neighbors.prev;
    if (target) {
      navigate(`/annotate/${target}`);
    } else if (asset?.dataset_id) {
      navigate(`/datasets/${asset.dataset_id}`);
    }
  }

  if (!assetId) {
    return (
      <div className="flex items-center justify-center h-64 text-[var(--hud-text-muted)] font-mono text-sm">
        No asset selected. Navigate here from the dataset view.
      </div>
    );
  }

  const classificationAnn = annotations.find((a) => a.type === 'classification');
  const visibleAnns = annotations.filter((a) => a.type !== 'classification');

  // Normalized 0–1 area of a shape, as a percentage of the frame.
  function annoArea(ann) {
    const W = imgDims.w || 1;
    const H = imgDims.h || 1;
    if (ann.type === 'box') {
      const { w, h } = ann.geometry;
      return ((w * h) / (W * H)) * 100;
    }
    if (ann.type === 'polygon') {
      const pts = ann.geometry.points || [];
      let a = 0;
      for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
        a += pts[j].x * pts[i].y - pts[i].x * pts[j].y;
      }
      return (Math.abs(a / 2) / (W * H)) * 100;
    }
    return 0;
  }

  const frameNo = (neighbors.index ?? 0) + 1;
  const frameTotal = neighbors.total || frameNo;
  const fileName =
    asset?.filename || asset?.uri?.split('/').pop() || `frame_${frameNo}`;
  const frameLabel = imgDims.w ? `${fileName} · ${imgDims.w}×${imgDims.h}` : fileName;

  function handleExit() {
    if (dirty && !window.confirm('You have unsaved changes. Leave anyway?')) return;
    if (asset?.dataset_id) navigate(`/datasets/${asset.dataset_id}`);
    else navigate(-1);
  }

  const TOOLS = [
    { id: 'box', label: 'BOX', key: 'B' },
    { id: 'polygon', label: 'POLYGON', key: 'P' },
    { id: 'keypoint', label: 'KEYPOINT', key: 'K' },
    { id: 'classify', label: 'CLASSIFY', key: 'C' },
  ];

  const navBtn =
    'inline-flex h-7 items-center border border-[var(--hud-border-strong)] px-2.5 font-mono text-[0.6875rem] tracking-wide text-[var(--hud-text-primary)] transition-colors duration-100 hover:border-[var(--hud-border-accent)] hover:bg-[var(--hud-elevated)] disabled:opacity-30 disabled:pointer-events-none';

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-[var(--hud-base)] text-[var(--hud-text-primary)]"
      data-testid="annotator-container"
      role="application"
      aria-label="Annotator"
    >
      {/* Offscreen live region — keeps assistive tech + tests informed. */}
      <div className="sr-only" aria-live="polite">
        <span data-testid="status">{status}</span>
        <span data-testid="mode">{mode}</span>
        <span data-testid="asset-id">{assetId}</span>
        <span data-testid="frame-pos">
          {frameNo}/{frameTotal}
        </span>
      </div>

      {/* Toolbar */}
      <div className="flex flex-shrink-0 items-center justify-between border-b border-[var(--hud-border-default)] bg-[var(--hud-inset)] px-3.5 py-2">
        {/* Left — exit + context */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleExit}
            className="font-mono text-[0.6875rem] tracking-wide text-[var(--hud-text-muted)] transition-colors duration-100 hover:text-[var(--hud-text-primary)]"
          >
            ← EXIT
          </button>
          <span className="h-4 w-px bg-[var(--hud-border-strong)]" />
          <span className="label-overline">{'//'} {datasetName || 'dataset'}</span>
        </div>

        {/* Center — tools */}
        <div className="flex items-center gap-1.5">
          {TOOLS.map((t) => {
            const active = mode === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setMode(t.id)}
                aria-pressed={active}
                aria-label={`${t.label} tool`}
                title={t.key}
                className={[
                  'inline-flex h-7 items-center gap-2 border px-2.5 font-mono text-[0.6875rem] tracking-[0.06em] transition-colors duration-100',
                  active
                    ? 'border-[var(--hud-accent)] bg-[var(--hud-accent)] text-[oklch(0.10_0.008_240)]'
                    : 'border-[var(--hud-border-default)] bg-transparent text-[var(--hud-text-secondary)] hover:bg-[var(--hud-elevated)] hover:text-[var(--hud-text-primary)]',
                ].join(' ')}
              >
                {t.label}
                <span
                  className={[
                    'inline-flex h-3.5 min-w-3.5 items-center justify-center rounded-[2px] border px-0.5 text-[9px] leading-none',
                    active
                      ? 'border-[oklch(0.10_0.008_240/0.4)] text-[oklch(0.10_0.008_240)]'
                      : 'border-[var(--hud-border-strong)] text-[var(--hud-text-muted)]',
                  ].join(' ')}
                >
                  {t.key}
                </span>
              </button>
            );
          })}
        </div>

        {/* Right — dirty state + save */}
        <div className="flex items-center gap-3">
          {dirty ? (
            <span className="pulse-active font-mono text-[0.6875rem] text-[var(--hud-warning-text)]">
              ● UNSAVED
            </span>
          ) : (
            <span className="font-mono text-[0.6875rem] text-[var(--hud-success-text)]">
              ✓ saved
            </span>
          )}
          <button
            onClick={undo}
            title="Ctrl/Cmd+Z"
            className="h-7 border border-transparent px-2.5 font-mono text-[0.6875rem] tracking-wide text-[var(--hud-text-secondary)] transition-colors duration-100 hover:bg-[var(--hud-elevated)] hover:text-[var(--hud-text-primary)]"
          >
            UNDO
          </button>
          <button
            onClick={handleSave}
            disabled={!dirty}
            title="Ctrl/Cmd+S"
            className={[
              'h-7 border px-3 font-mono text-[0.6875rem] tracking-wide transition-colors duration-100',
              dirty
                ? 'border-[var(--hud-accent)] bg-[var(--hud-accent)] text-[oklch(0.10_0.008_240)] hover:bg-[var(--hud-accent-hover)] hover:border-[var(--hud-accent-hover)]'
                : 'cursor-not-allowed border-[var(--hud-border-default)] text-[var(--hud-text-muted)] opacity-40',
            ].join(' ')}
          >
            SAVE
          </button>
        </div>
      </div>

      {/* Body — 180 / 1fr / 240 */}
      <div className="grid min-h-0 flex-1 [grid-template-columns:180px_1fr_240px]">
        {/* Left — Classes */}
        <div className="flex min-h-0 flex-col border-r border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
          <div className="border-b border-[var(--hud-border-subtle)] px-3 py-2.5">
            <span className="label-overline">Classes</span>
          </div>
          <div className="flex-1 overflow-y-auto">
            {classes.map((cls, i) => {
              const color = CLASS_COLORS[i % CLASS_COLORS.length];
              const active =
                mode === 'classify'
                  ? classificationAnn?.class_name === cls
                  : selectedClass === cls;
              return (
                <button
                  key={cls}
                  onClick={() => {
                    if (mode === 'classify') {
                      applyClassification(cls);
                      return;
                    }
                    setSelectedClass(cls);
                    // Reassign the selected shape's class when one is active.
                    if (selectedAnnotationIdx != null) {
                      setAnnotationClass(selectedAnnotationIdx, cls);
                    }
                  }}
                  aria-pressed={active}
                  className={[
                    'flex w-full items-center gap-2 px-3 py-2 text-left transition-colors duration-100',
                    active ? 'bg-[var(--hud-accent-dim)]' : 'hover:bg-[var(--hud-elevated)]',
                  ].join(' ')}
                  style={{ borderLeft: `2px solid ${active ? color : 'transparent'}` }}
                >
                  <span
                    className="inline-block flex-shrink-0"
                    style={{ width: 10, height: 10, background: color }}
                  />
                  <span
                    className="flex-1 truncate font-mono text-[11.5px]"
                    style={{
                      color: active
                        ? 'var(--hud-text-primary)'
                        : 'var(--hud-text-secondary)',
                    }}
                  >
                    {cls}
                  </span>
                  <span className="font-mono text-[9px] text-[var(--hud-text-muted)]">
                    {i + 1}
                  </span>
                </button>
              );
            })}
            {mode === 'classify' && classificationAnn && (
              <p className="px-3 py-2 font-mono text-[0.6875rem] text-[var(--hud-success-text)]">
                ✓ {classificationAnn.class_name}
              </p>
            )}
          </div>
          <div className="space-y-2 border-t border-[var(--hud-border-subtle)] p-2">
            {showAddClass && (
              <input
                type="text"
                autoFocus
                value={newClassName}
                onChange={(e) => setNewClassName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') addClass();
                  else if (e.key === 'Escape') setShowAddClass(false);
                }}
                placeholder="class name…"
                aria-label="New class name"
                className="w-full border border-[var(--hud-border-default)] bg-[var(--hud-inset)] px-2 py-1 font-mono text-xs text-[var(--hud-text-primary)] focus:outline-none focus:border-[var(--hud-border-accent)] focus:ring-1 focus:ring-[var(--hud-accent)]"
              />
            )}
            <button
              onClick={() => {
                if (showAddClass) addClass();
                else setShowAddClass(true);
              }}
              className="w-full border border-[var(--hud-border-strong)] px-2 py-1 font-mono text-[0.6875rem] tracking-wide text-[var(--hud-text-secondary)] transition-colors duration-100 hover:border-[var(--hud-border-accent)] hover:bg-[var(--hud-elevated)] hover:text-[var(--hud-text-primary)]"
            >
              + ADD CLASS
            </button>
          </div>
        </div>

        {/* Center — canvas + frame nav */}
        <div className="flex min-h-0 min-w-0 flex-col">
          <div
            className="relative flex flex-1 items-center justify-center overflow-auto"
            style={{ background: 'var(--hud-inset)', padding: 24 }}
          >
            {!imageError && (
              <div className="pointer-events-none absolute left-6 top-6 z-10 bg-[oklch(0.10_0.008_240/0.7)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--hud-text-muted)]">
                {frameLabel}
              </div>
            )}
            {imageError ? (
              <div
                className="flex flex-col items-center gap-2"
                style={{ color: 'var(--hud-text-muted)' }}
              >
                <div
                  className="flex h-24 w-24 items-center justify-center border font-mono text-3xl"
                  style={{
                    background: 'var(--hud-surface)',
                    borderColor: 'var(--hud-border-default)',
                  }}
                >
                  ?
                </div>
                <p className="font-mono text-xs">Image could not be loaded</p>
                <p className="font-mono text-[0.6875rem]">{assetId}</p>
              </div>
            ) : (
              <canvas
                ref={canvasRef}
                className={
                  mode === 'box' || mode === 'polygon' || mode === 'keypoint'
                    ? 'cursor-crosshair'
                    : 'cursor-pointer'
                }
                style={{
                  display: 'block',
                  maxWidth: '100%',
                  maxHeight: '100%',
                  border: '1px solid var(--hud-border-strong)',
                }}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={() => {
                  if (drawingRef.current.active) {
                    drawingRef.current = {
                      active: false,
                      startX: 0,
                      startY: 0,
                      currentX: 0,
                      currentY: 0,
                    };
                    redraw();
                  }
                }}
                data-testid="annotation-canvas"
              />
            )}
          </div>

          {/* Frame nav */}
          <div className="flex flex-shrink-0 items-center justify-between border-t border-[var(--hud-border-default)] bg-[var(--hud-surface)] px-4 py-2">
            <button
              className={navBtn}
              onClick={() => navigateAsset(-1)}
              disabled={!neighbors.prev}
              aria-label="Previous frame"
            >
              ← PREV
            </button>
            <div className="font-mono text-[0.6875rem] text-[var(--hud-text-muted)]">
              FRAME <span className="text-[var(--hud-accent)]">{frameNo}</span> / {frameTotal}
              {' · '}
              <span className="text-[var(--hud-text-secondary)]">
                {visibleAnns.length} annotations
              </span>
            </div>
            <button
              className={navBtn}
              onClick={() => navigateAsset(1)}
              disabled={!neighbors.next}
              aria-label="Next frame"
            >
              NEXT →
            </button>
          </div>
        </div>

        {/* Right — Annotations */}
        <div className="flex min-h-0 flex-col border-l border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
          <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] px-3 py-2.5">
            <span className="label-overline">Annotations</span>
            <span className="font-mono text-[0.6875rem] text-[var(--hud-text-data)]">
              {visibleAnns.length}
            </span>
          </div>
          <div className="flex-1 overflow-y-auto">
            {visibleAnns.length === 0 ? (
              <p className="px-3 py-3 text-[12px] text-[var(--hud-text-muted)]">
                Drag on the frame to draw a box.
              </p>
            ) : (
              annotations.map((ann, idx) => {
                if (ann.type === 'classification') return null;
                const color = classColor(ann.class_name, classes);
                const sel = idx === selectedAnnotationIdx;
                return (
                  <div
                    key={idx}
                    onClick={() => setSelectedAnnotationIdx(sel ? null : idx)}
                    role="option"
                    aria-selected={sel}
                    className={[
                      'group flex cursor-pointer items-center gap-2 border-b border-[var(--hud-border-subtle)] px-3 py-2 transition-colors duration-100',
                      sel ? 'bg-[var(--hud-accent-dim)]' : 'hover:bg-[var(--hud-elevated)]',
                    ].join(' ')}
                  >
                    <span
                      className="inline-block flex-shrink-0"
                      style={{ width: 9, height: 9, background: color }}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-mono text-[11.5px] text-[var(--hud-text-primary)]">
                        {ann.class_name}
                      </div>
                      <div className="font-mono text-[9px] text-[var(--hud-text-muted)]">
                        {annoArea(ann).toFixed(1)}% area
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteAnnotation(idx);
                      }}
                      aria-label={`Delete annotation ${idx}`}
                      title="Delete"
                      className="px-1 font-mono text-[var(--hud-text-muted)] transition-colors duration-100 hover:text-[var(--hud-danger-text)]"
                    >
                      ✕
                    </button>
                  </div>
                );
              })
            )}
          </div>
          <div className="space-y-1 border-t border-[var(--hud-border-subtle)] px-3 py-2 font-mono text-[10px]">
            <div className="flex items-center justify-between">
              <span className="text-[var(--hud-text-muted)]">TOOL</span>
              <span className="text-[var(--hud-text-accent)]">→ {mode.toUpperCase()}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[var(--hud-text-muted)]">CLASS</span>
              <span className="truncate text-[var(--hud-text-accent)]">→ {selectedClass}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
