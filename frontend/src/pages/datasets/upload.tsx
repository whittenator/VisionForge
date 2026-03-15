import React, { useState, useRef } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';
import Spinner from '@/components/ui/Spinner';
import { apiPost } from '@/services/api';

interface UploadEntry {
  name: string;
  progress: number;
  status: 'pending' | 'uploading' | 'done' | 'error';
  error?: string;
}

export default function DatasetUpload() {
  const [searchParams] = useSearchParams();
  const projectId = searchParams.get('projectId') || '';
  const datasetId = searchParams.get('datasetId') || '';
  const versionId = searchParams.get('versionId') || '';

  const [files, setFiles] = useState<File[]>([]);
  const [uploads, setUploads] = useState<UploadEntry[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [allDone, setAllDone] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files || []);
    setFiles(selected);
    setUploads([]);
    setAllDone(false);
    setError(null);
  }

  function onDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    const dropped = Array.from(e.dataTransfer.files);
    setFiles(dropped);
    setUploads([]);
    setAllDone(false);
    setError(null);
  }

  function onDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
  }

  async function onUpload() {
    if (!files.length) return;
    if (!datasetId || !versionId) {
      setError('Missing datasetId or versionId. Use ?datasetId=...&versionId=... query params.');
      return;
    }
    setUploading(true);
    setError(null);
    setAllDone(false);

    const initial: UploadEntry[] = files.map((f) => ({
      name: f.name,
      progress: 0,
      status: 'pending',
    }));
    setUploads(initial);

    let hasError = false;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];

      setUploads((prev) =>
        prev.map((u, idx) => (idx === i ? { ...u, status: 'uploading' } : u))
      );

      try {
        // 1. Get presigned URL
        const { url, objectKey } = await apiPost<{
          url: string;
          fields: Record<string, string>;
          objectKey: string;
        }>('/api/ingest/upload-url', {
          datasetVersionId: versionId,
          filename: file.name,
          contentType: file.type,
        });

        // 2. Upload directly to MinIO with XHR progress tracking
        await new Promise<void>((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
              const pct = Math.round((e.loaded / e.total) * 100);
              setUploads((prev) =>
                prev.map((u, idx) => (idx === i ? { ...u, progress: pct } : u))
              );
            }
          };
          xhr.onload = () => {
            if (xhr.status < 300) {
              resolve();
            } else {
              reject(new Error(`Upload failed: ${xhr.status} ${xhr.statusText}`));
            }
          };
          xhr.onerror = () => reject(new Error('Network error during upload'));
          xhr.open('PUT', url);
          xhr.setRequestHeader('Content-Type', file.type);
          xhr.send(file);
        });

        // 3. Confirm upload — register asset in DB
        await apiPost('/api/ingest/confirm', {
          dataset_id: datasetId,
          version_id: versionId,
          storage_key: objectKey,
          filename: file.name,
          content_type: file.type,
        });

        setUploads((prev) =>
          prev.map((u, idx) => (idx === i ? { ...u, progress: 100, status: 'done' } : u))
        );
      } catch (err) {
        hasError = true;
        const msg = err instanceof Error ? err.message : 'Upload failed';
        setUploads((prev) =>
          prev.map((u, idx) => (idx === i ? { ...u, status: 'error', error: msg } : u))
        );
        setError(msg);
      }
    }

    setUploading(false);
    if (!hasError) setAllDone(true);
  }

  const doneCount = uploads.filter((u) => u.status === 'done').length;

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Upload Dataset Assets</h1>
        {projectId && (
          <Link
            className="text-sm text-blue-600 hover:underline"
            to={`/projects/${projectId}`}
          >
            Back to Project
          </Link>
        )}
      </div>

      {!datasetId || !versionId ? (
        <Alert variant="warning">
          No dataset/version selected. Pass <code>?datasetId=...&amp;versionId=...</code> in the
          URL, or navigate here from a dataset page.
        </Alert>
      ) : (
        <p className="text-sm text-muted-foreground">
          Uploading to dataset <code className="font-mono">{datasetId}</code>, version{' '}
          <code className="font-mono">{versionId}</code>
        </p>
      )}

      <Card>
        <CardContent className="pt-4">
          {/* Drop zone */}
          <div
            onDrop={onDrop}
            onDragOver={onDragOver}
            onClick={() => fileInputRef.current?.click()}
            className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-border p-10 cursor-pointer hover:bg-muted/30 transition-colors"
          >
            <svg
              className="mb-2 h-10 w-10 text-muted-foreground"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
              />
            </svg>
            <p className="text-sm font-medium">Drop files here or click to browse</p>
            <p className="text-xs text-muted-foreground mt-1">
              Images, videos, or annotation files
            </p>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={onFileChange}
            />
          </div>

          {files.length > 0 && uploads.length === 0 && (
            <p className="mt-3 text-sm text-muted-foreground">
              {files.length} file(s) selected
            </p>
          )}

          {/* Progress list */}
          {uploads.length > 0 && (
            <ul className="mt-4 space-y-3">
              {uploads.map((u, i) => (
                <li key={i} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="truncate max-w-xs">{u.name}</span>
                    <span
                      className={
                        u.status === 'done'
                          ? 'text-green-600'
                          : u.status === 'error'
                          ? 'text-red-600'
                          : 'text-muted-foreground'
                      }
                    >
                      {u.status === 'done'
                        ? '✓ Done'
                        : u.status === 'error'
                        ? '✗ Error'
                        : u.status === 'uploading'
                        ? `${u.progress}%`
                        : 'Pending'}
                    </span>
                  </div>
                  <div className="h-1.5 w-full rounded bg-muted overflow-hidden">
                    <div
                      style={{ width: `${u.progress}%` }}
                      className={`h-full rounded transition-all ${
                        u.status === 'error' ? 'bg-red-500' : 'bg-blue-600'
                      }`}
                    />
                  </div>
                  {u.error && (
                    <p className="text-xs text-red-600">{u.error}</p>
                  )}
                </li>
              ))}
            </ul>
          )}

          {error && (
            <Alert variant="error" className="mt-3">
              {error}
            </Alert>
          )}

          <div className="mt-4 flex items-center gap-3">
            <Button
              onClick={onUpload}
              disabled={
                files.length === 0 || uploading || !datasetId || !versionId
              }
            >
              {uploading ? (
                <span className="flex items-center gap-2">
                  <Spinner />
                  Uploading {doneCount}/{files.length}…
                </span>
              ) : (
                `Upload ${files.length > 0 ? `${files.length} file(s)` : ''}`
              )}
            </Button>

            {allDone && (
              <span className="text-sm text-green-600 font-medium">
                All {doneCount} file(s) uploaded successfully!
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {allDone && datasetId && (
        <div className="flex gap-3">
          {projectId && (
            <Button variant="outline" as="a">
              <Link to={`/projects/${projectId}`}>Go to Project</Link>
            </Button>
          )}
          <Link
            to={`/datasets/version?datasetId=${datasetId}`}
            className="inline-flex items-center rounded-md border border-gray-300 bg-white px-4 h-9 text-sm hover:bg-gray-50"
          >
            Create Snapshot
          </Link>
        </div>
      )}
    </div>
  );
}
