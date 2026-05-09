import React, { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';
import Spinner from '@/components/ui/Spinner';
import { apiGet, apiUrl } from '@/services/api';
import { getStoredToken } from '@/services/token-store';

interface ModelArtifact {
  id: string;
  name: string;
  version: string;
  type: string;
  format: string;
}

interface PredictResponse {
  model_id: string;
  model_name: string;
  model_version: string;
  result: {
    detections?: Array<{ class: string; bbox: [number, number, number, number]; score: number }>;
    classification?: { class: string; score: number };
    raw_shape?: number[];
    top_class_index?: number;
    top_score?: number;
  };
}

export default function ArtifactsPredict() {
  const { modelId } = useParams();
  const [model, setModel] = useState<ModelArtifact | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  useEffect(() => {
    if (!modelId) return;
    apiGet<ModelArtifact>(`/api/artifacts/models/${modelId}`).then(setModel).catch(() => {});
  }, [modelId]);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  useEffect(() => {
    if (!previewUrl || !canvasRef.current) return;
    const img = new Image();
    img.onload = () => {
      const canvas = canvasRef.current!;
      const w = Math.min(800, img.naturalWidth);
      const scale = w / img.naturalWidth;
      canvas.width = w;
      canvas.height = img.naturalHeight * scale;
      const ctx = canvas.getContext('2d')!;
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      imgRef.current = img;
      drawDetections(scale);
    };
    img.src = previewUrl;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewUrl, result]);

  function drawDetections(scale: number) {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d')!;
    const detections = result?.result?.detections || [];
    detections.forEach((d, i) => {
      const [x, y, w, h] = d.bbox;
      const color = `oklch(0.72 0.10 ${(i * 47) % 360})`;
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(x * scale, y * scale, w * scale, h * scale);
      const label = `${d.class} ${(d.score * 100).toFixed(0)}%`;
      ctx.font = '12px monospace';
      const tw = ctx.measureText(label).width + 8;
      ctx.fillStyle = color;
      ctx.fillRect(x * scale, y * scale - 16, tw, 16);
      ctx.fillStyle = '#000';
      ctx.fillText(label, x * scale + 4, y * scale - 4);
    });
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !modelId) {
      setError('Pick an image');
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('score_threshold', '0.25');
      const token = getStoredToken();
      const res = await fetch(apiUrl(`/api/artifacts/models/${modelId}/predict`), {
        method: 'POST',
        body: fd,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail || `HTTP ${res.status}`);
      }
      const json = (await res.json()) as PredictResponse;
      setResult(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Prediction failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
        <div>
          <div className="label-overline mb-0.5">// Artifacts / Predict</div>
          <h1>Predict with model</h1>
          {model && (
            <p className="text-xs font-mono text-[var(--hud-text-muted)] mt-1">
              {model.name} v{model.version} · {model.format}
            </p>
          )}
        </div>
        <Link
          to="/artifacts"
          className="text-xs font-mono text-[var(--hud-accent)] hover:underline"
        >
          ← ARTIFACTS
        </Link>
      </div>

      <form onSubmit={onSubmit} className="space-y-3">
        <div>
          <label className="label-overline block mb-1">Image</label>
          <input
            type="file"
            accept="image/*"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="text-xs font-mono"
          />
        </div>
        {error && <Alert variant="error">{error}</Alert>}
        <Button type="submit" disabled={loading || !file}>
          {loading ? (
            <span className="flex items-center gap-2">
              <Spinner size={12} /> Running…
            </span>
          ) : (
            'Run prediction'
          )}
        </Button>
      </form>

      {previewUrl && (
        <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] p-3">
          <canvas ref={canvasRef} style={{ maxWidth: '100%', display: 'block' }} />
        </div>
      )}

      {result && (
        <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)] p-3 space-y-2">
          <div className="label-overline">Predictions</div>
          {result.result.classification && (
            <div className="text-sm font-mono">
              <span className="text-[var(--hud-text-muted)]">Top class:</span>{' '}
              <span className="text-[var(--hud-text-data)]">
                {result.result.classification.class}
              </span>{' '}
              ({(result.result.classification.score * 100).toFixed(1)}%)
            </div>
          )}
          {result.result.detections && result.result.detections.length > 0 && (
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="text-[var(--hud-text-muted)]">
                  <th className="text-left p-1">CLASS</th>
                  <th className="text-left p-1">SCORE</th>
                  <th className="text-left p-1">BBOX</th>
                </tr>
              </thead>
              <tbody>
                {result.result.detections.map((d, i) => (
                  <tr key={i} className="border-t border-[var(--hud-border-subtle)]">
                    <td className="p-1 text-[var(--hud-text-data)]">{d.class}</td>
                    <td className="p-1">{(d.score * 100).toFixed(1)}%</td>
                    <td className="p-1 text-[var(--hud-text-muted)]">
                      [{d.bbox.map((v) => v.toFixed(0)).join(', ')}]
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {result.result.top_class_index != null && (
            <div className="text-sm font-mono">
              <span className="text-[var(--hud-text-muted)]">Top index:</span>{' '}
              <span className="text-[var(--hud-text-data)]">
                {result.result.top_class_index}
              </span>{' '}
              ({((result.result.top_score || 0) * 100).toFixed(1)}%)
            </div>
          )}
        </div>
      )}
    </div>
  );
}
