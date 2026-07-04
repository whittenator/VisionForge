import React, { useEffect, useState } from 'react';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Alert from '@/components/ui/Alert';
import { apiGet, apiPut, apiPost } from '@/services/api';

interface Workspace {
  id: string;
  name: string;
}

interface StorageConfig {
  endpoint: string | null;
  region: string | null;
  bucket: string | null;
  access_key: string | null;
  secret_key: string | null;
  secret_key_set?: boolean;
  secure: boolean | null;
}

interface StorageSettings {
  backend: string;
  config: StorageConfig;
}

interface TestResult {
  ok: boolean;
  detail: string;
}

const BACKENDS: Array<{ value: string; label: string }> = [
  { value: 'minio', label: 'MinIO' },
  { value: 's3', label: 'Amazon S3 (or compatible)' },
];

const EMPTY_CONFIG: StorageConfig = {
  endpoint: '',
  region: '',
  bucket: '',
  access_key: '',
  secret_key: '',
  secure: false,
};

export default function StorageSettingsPage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  const [backend, setBackend] = useState<string>('minio');
  const [config, setConfig] = useState<StorageConfig>(EMPTY_CONFIG);
  const [secretSet, setSecretSet] = useState(false);

  useEffect(() => {
    apiGet<Workspace[]>('/api/workspaces')
      .then((ws) => {
        setWorkspaces(ws);
        if (ws.length > 0) setSelectedWorkspace(ws[0].id);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load workspaces'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedWorkspace) return;
    setSettingsLoading(true);
    setError(null);
    setSuccess(null);
    setTestResult(null);
    apiGet<StorageSettings>(`/api/settings/workspaces/${selectedWorkspace}/storage`)
      .then((s) => {
        setBackend(s.backend || 'minio');
        setConfig({
          endpoint: s.config.endpoint ?? '',
          region: s.config.region ?? '',
          bucket: s.config.bucket ?? '',
          access_key: s.config.access_key ?? '',
          secret_key: '',
          secure: Boolean(s.config.secure),
        });
        setSecretSet(Boolean(s.config.secret_key_set));
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : 'Failed to load storage settings')
      )
      .finally(() => setSettingsLoading(false));
  }, [selectedWorkspace]);

  function updateField<K extends keyof StorageConfig>(key: K, value: StorageConfig[K]) {
    setConfig((prev) => ({ ...prev, [key]: value }));
  }

  function buildPayload() {
    const payload: Record<string, unknown> = {
      endpoint: config.endpoint || null,
      region: config.region || null,
      bucket: config.bucket || null,
      access_key: config.access_key || null,
      secure: Boolean(config.secure),
    };
    // Only send the secret when the user typed a new one; omitting it preserves
    // the stored value server-side.
    if (config.secret_key) payload.secret_key = config.secret_key;
    return { backend, config: payload };
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedWorkspace) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const saved = await apiPut<StorageSettings>(
        `/api/settings/workspaces/${selectedWorkspace}/storage`,
        buildPayload()
      );
      setBackend(saved.backend || 'minio');
      setSecretSet(Boolean(saved.config.secret_key_set));
      setConfig((prev) => ({ ...prev, secret_key: '' }));
      setSuccess('Storage settings saved.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save storage settings');
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    if (!selectedWorkspace) return;
    setTesting(true);
    setError(null);
    setTestResult(null);
    try {
      const result = await apiPost<TestResult>(
        `/api/settings/workspaces/${selectedWorkspace}/storage/test`,
        buildPayload()
      );
      setTestResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Connection test failed');
    } finally {
      setTesting(false);
    }
  }

  const isS3 = backend === 's3';

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="border-b border-[var(--hud-border-subtle)] pb-3">
        <div className="label-overline mb-0.5">// Settings / Storage</div>
        <h1>Object Storage</h1>
      </div>

      {error && <Alert variant="error">{error}</Alert>}
      {success && <Alert variant="success">{success}</Alert>}

      {/* Workspace selector */}
      {workspaces.length > 1 && (
        <div className="flex items-center gap-3">
          <label htmlFor="workspace-select" className="label-overline whitespace-nowrap">
            Workspace
          </label>
          <Select
            id="workspace-select"
            value={selectedWorkspace}
            onChange={(e) => setSelectedWorkspace(e.target.value)}
            className="max-w-xs"
          >
            {workspaces.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </Select>
        </div>
      )}

      {loading ? (
        <div className="py-6 text-sm text-[var(--hud-text-muted)]">Loading workspaces…</div>
      ) : workspaces.length === 0 ? (
        <Alert variant="info">You do not belong to any workspace yet.</Alert>
      ) : (
        <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
          <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center gap-2">
            <div className="h-1.5 w-1.5 bg-[var(--hud-accent)]" />
            <span className="label-overline">Storage Backend</span>
          </div>

          {settingsLoading ? (
            <div className="px-4 py-4 text-sm text-[var(--hud-text-muted)]">Loading settings…</div>
          ) : (
            <form onSubmit={handleSave} className="p-4 space-y-4" aria-label="Storage settings form">
              <div className="space-y-1 max-w-xs">
                <label htmlFor="backend" className="label-overline block">
                  Backend
                </label>
                <Select
                  id="backend"
                  aria-label="Backend"
                  value={backend}
                  onChange={(e) => setBackend(e.target.value)}
                >
                  {BACKENDS.map((b) => (
                    <option key={b.value} value={b.value}>
                      {b.label}
                    </option>
                  ))}
                </Select>
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-1">
                  <label htmlFor="endpoint" className="label-overline block">
                    Endpoint
                  </label>
                  <Input
                    id="endpoint"
                    aria-label="Endpoint"
                    placeholder={isS3 ? 's3.amazonaws.com' : 'minio:9000'}
                    value={config.endpoint ?? ''}
                    onChange={(e) => updateField('endpoint', e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <label htmlFor="region" className="label-overline block">
                    Region
                  </label>
                  <Input
                    id="region"
                    aria-label="Region"
                    placeholder="us-east-1"
                    value={config.region ?? ''}
                    onChange={(e) => updateField('region', e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <label htmlFor="bucket" className="label-overline block">
                    Bucket
                  </label>
                  <Input
                    id="bucket"
                    aria-label="Bucket"
                    placeholder="visionforge"
                    value={config.bucket ?? ''}
                    onChange={(e) => updateField('bucket', e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <label htmlFor="access-key" className="label-overline block">
                    Access Key
                  </label>
                  <Input
                    id="access-key"
                    aria-label="Access Key"
                    value={config.access_key ?? ''}
                    onChange={(e) => updateField('access_key', e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <label htmlFor="secret-key" className="label-overline block">
                    Secret Key
                  </label>
                  <Input
                    id="secret-key"
                    aria-label="Secret Key"
                    type="password"
                    placeholder={secretSet ? '•••••••• (unchanged)' : 'Enter secret key'}
                    value={config.secret_key ?? ''}
                    onChange={(e) => updateField('secret_key', e.target.value)}
                  />
                  {secretSet && (
                    <p className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)]">
                      A secret is stored. Leave blank to keep it.
                    </p>
                  )}
                </div>
                <div className="space-y-1">
                  <label htmlFor="secure" className="label-overline block">
                    TLS
                  </label>
                  <label className="flex items-center gap-2 text-sm text-[var(--hud-text-primary)] h-8">
                    <input
                      id="secure"
                      aria-label="Use TLS"
                      type="checkbox"
                      checked={Boolean(config.secure)}
                      onChange={(e) => updateField('secure', e.target.checked)}
                    />
                    Use HTTPS / secure connection
                  </label>
                </div>
              </div>

              {testResult && (
                <Alert variant={testResult.ok ? 'success' : 'error'}>{testResult.detail}</Alert>
              )}

              <div className="flex items-center gap-3 pt-2">
                <Button type="submit" disabled={saving}>
                  {saving ? 'Saving…' : 'Save'}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleTest}
                  disabled={testing}
                  aria-label="Test connection"
                >
                  {testing ? 'Testing…' : 'Test connection'}
                </Button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
