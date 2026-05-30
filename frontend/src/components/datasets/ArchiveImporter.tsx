import React, { useEffect, useState } from 'react';
import Select from '@/components/ui/Select';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';
import Spinner from '@/components/ui/Spinner';
import { apiGet, apiUrl } from '@/services/api';
import { getStoredToken } from '@/services/token-store';

export interface ImportResult {
  dataset_id: string;
  version_id: string;
  format: string;
  asset_count: number;
  annotation_count: number;
  classes: string[];
  warnings: string[];
}

interface ArchiveImporterProps {
  datasetId: string;
  /** Target an existing open version; omit to let the backend create one. */
  versionId?: string;
  onComplete?: (result: ImportResult) => void;
}

const DEFAULT_FORMATS = ['coco', 'yolo', 'pascal_voc', 'cvat', 'labelme', 'datumaro'];

/**
 * Imports a labeled archive (zip) into a dataset via `/api/datasets/{id}/import`.
 * Uses a raw multipart fetch (the api.ts helpers are JSON-only). Extracted from
 * the legacy import page so it can be embedded in the wizard and detail tab.
 */
export default function ArchiveImporter({
  datasetId,
  versionId,
  onComplete,
}: ArchiveImporterProps) {
  const [formats, setFormats] = useState<string[]>(DEFAULT_FORMATS);
  const [fmt, setFmt] = useState('coco');
  const [imageUriBase, setImageUriBase] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    apiGet<{ formats: string[] }>('/api/datasets/formats')
      .then((r) => r.formats?.length && setFormats(r.formats))
      .catch(() => {});
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!datasetId || !file) {
      setError('Pick an archive to import');
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
      onComplete?.(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed');
    } finally {
      setLoading(false);
    }
  }

  if (result) {
    return (
      <Alert variant="success">
        Imported {result.asset_count} assets and {result.annotation_count} annotations (
        {result.classes.length} classes) into version{' '}
        <span className="font-mono">{result.version_id.slice(0, 8)}</span>.
        {result.warnings.length > 0 && (
          <div className="mt-2 text-[0.6875rem] font-mono">
            {result.warnings.length} warning{result.warnings.length !== 1 ? 's' : ''}
          </div>
        )}
        <div className="mt-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setResult(null);
              setFile(null);
            }}
          >
            Import another
          </Button>
        </div>
      </Alert>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <p className="text-xs text-[var(--hud-text-muted)]">
        Upload a zip in COCO, YOLO, Pascal VOC, CVAT, LabelMe, or Datumaro format. Images and labels
        are added to the open version.
      </p>
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
      <Button type="submit" disabled={loading || !file}>
        {loading ? (
          <span className="flex items-center gap-2">
            <Spinner size={12} /> Importing…
          </span>
        ) : (
          'Import archive'
        )}
      </Button>
    </form>
  );
}
