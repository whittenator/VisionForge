import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Alert from '@/components/ui/Alert';
import Button from '@/components/ui/Button';
import { apiPost } from '@/services/api';

interface Job {
  id: string;
  status: string;
  createdAt: string;
}

export default function ArtifactsExport() {
  const { modelId } = useParams<{ modelId: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleExport() {
    if (!modelId) return;
    setLoading(true);
    try {
      const j = await apiPost<Job>(`/api/artifacts/models/${modelId}/export`);
      setJob(j);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader><CardTitle>Export Model</CardTitle></CardHeader>
      <CardContent>
        <Button onClick={handleExport} disabled={loading || !modelId}>
          {loading ? 'Exporting...' : 'Export ONNX'}
        </Button>
        {job && <Alert variant="info" className="mt-3">Export job {job.id} status: {job.status}</Alert>}
      </CardContent>
    </Card>
  );
}
