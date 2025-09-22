import React, { useState } from 'react';
import AppShell from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';

export default function DatasetVersion() {
  const [message, setMessage] = useState<string | null>(null);

  function createSnapshot() {
    setMessage('Dataset snapshot created');
  }

  return (
    <AppShell>
      <Card>
        <CardHeader><CardTitle>Dataset Version Snapshot</CardTitle></CardHeader>
        <CardContent>
          <Button onClick={createSnapshot}>Create Snapshot</Button>
          {message ? <Alert variant="success" className="mt-3">{message}</Alert> : null}
        </CardContent>
      </Card>
    </AppShell>
  );
}
