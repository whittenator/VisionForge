import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import AppShell from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Alert from '@/components/ui/Alert';

export default function ArtifactsExport() {
  const [params] = useSearchParams();
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    const id = params.get('id') || 'unknown';
    setMsg(`ONNX export requested for artifact ${id}`);
  }, [params]);

  return (
    <AppShell>
      <Card>
        <CardHeader><CardTitle>Export ONNX</CardTitle></CardHeader>
        <CardContent>
          {msg ? <Alert variant="info">{msg}</Alert> : null}
        </CardContent>
      </Card>
    </AppShell>
  );
}
