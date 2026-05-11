import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import Select from '@/components/ui/Select';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';
import Spinner from '@/components/ui/Spinner';
import { apiGet, apiUrl } from '@/services/api';
import { getStoredToken } from '@/services/token-store';

interface DatasetSummary {
  id: string;
  name: string;
  latest_version_id?: string | null;
}

interface ImportResult {
  dataset_id: string;
  version_id: string;
  format: string;
  asset_count: number;
  annotation_count: number;
  classes: string[];
  warnings: string[];
}

export default function DatasetImport() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [formats, setFormats] = useState<string[]>([
    'coco',
    'yolo',
    'pascal_voc',
    'cvat',
    'labelme',
    'datumaro',
  ]);
  const [datasetId, setDatasetId] = useState(params.get('datasetId') || '');
  const [fmt, setFmt] = useState('coco');
  const [versionId, setVersionId] = useState('');
  const [imageUriBase, setImageUriBase] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    apiGet<{ items: DatasetSummary[] }>('/api/datasets?page=1&page_size=200')
      .then((d) => setDatasets(d.items || []))
      .catch(() => {});
    apiGet<{ formats: string[] }>('/api/datasets/formats')
      .then((r) => setFormats(r.formats))
      .catch(() => {});
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!datasetId || !file) {
      setError('Pick a dataset and an archive');
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('fmt', fmt);
      if (versionId) fd.append('version_id', versionId);
      if (imageUriBase) fd.append('image_uri_base', imageUriBase);
      const token = getStoredToken();
      const res = await fetch(apiUrl(`/api/datasets/${datasetId}/import`), {
        method: 'POST',
        body: fd,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail || `HTTP ${res.status}`);
      }
      const json = (await res.json()) as ImportResult;
      setResult(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-xl space-y-4">
      <div className="flex items-center justify-between border-b border-[var(--hud-border-subtle)] pb-3">
        <div>
          <div className="label-overline mb-0.5">// Datasets / Import</div>
          <h1>Import dataset archive</h1>
          <p className="text-xs text-[var(--hud-text-muted)] mt-1">
            Upload a zip in COCO, YOLO, Pascal VOC, CVAT, LabelMe, or Datumaro format.
          </p>
        </div>
        <Link
          to="/datasets"
          className="text-xs font-mono text-[var(--hud-accent)] hover:underline"
        >
          ← DATASETS
        </Link>
      </div>

      {result ? (
        <Alert variant="success">
          Imported {result.asset_count} assets and {result.annotation_count} annotations
          ({result.classes.length} classes) into version{' '}
          <span className="font-mono">{result.version_id.slice(0, 8)}</span>.
          {result.warnings.length > 0 && (
            <div className="mt-2 text-[0.6875rem] font-mono">
              {result.warnings.length} warning{result.warnings.length !== 1 ? 's' : ''}
            </div>
          )}
          <div className="mt-3 flex gap-2">
            <Button onClick={() => navigate(`/datasets/${result.dataset_id}`)}>
              Open dataset
            </Button>
            <Button variant="outline" onClick={() => setResult(null)}>
              Import another
            </Button>
          </div>
        </Alert>
      ) : (
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <label className="label-overline block mb-1">Target dataset</label>
            <Select value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
              <option value="">— select —</option>
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <label className="label-overline block mb-1">Format</label>
            <Select value={fmt} onChange={(e) => setFmt(e.target.value)}>
              {formats.map((f) => (
                <option key={f} value={f}>
                  {f.toUpperCase()}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <label className="label-overline block mb-1">Existing version ID (optional)</label>
            <Input
              value={versionId}
              onChange={(e) => setVersionId(e.target.value)}
              placeholder="leave blank to create a new version"
            />
          </div>
          <div>
            <label className="label-overline block mb-1">Image URI base (optional)</label>
            <Input
              value={imageUriBase}
              onChange={(e) => setImageUriBase(e.target.value)}
              placeholder="e.g. datasets/<id>/imported/"
            />
          </div>
          <div>
            <label className="label-overline block mb-1">Archive (zip)</label>
            <input
              type="file"
              accept=".zip,application/zip"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="text-xs font-mono"
            />
          </div>
          {error && <Alert variant="error">{error}</Alert>}
          <Button type="submit" disabled={loading || !file || !datasetId}>
            {loading ? (
              <span className="flex items-center gap-2">
                <Spinner size={12} /> Importing…
              </span>
            ) : (
              'Import'
            )}
          </Button>
        </form>
      )}
    </div>
  );
}
