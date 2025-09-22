import React, { useState } from 'react';
import AppShell from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';

export default function DatasetUpload() {
  const [files, setFiles] = useState<File[]>([]);
  const [msg, setMsg] = useState<string | null>(null);

  function onChange(e: React.ChangeEvent<HTMLInputElement>) {
    setFiles(Array.from(e.target.files || []));
  }

  async function onUpload() {
    if (files.length === 0) return;
    // Presign stub: in a real app call backend to get presigned PUT urls and upload.
    setMsg(`Queued ${files.length} file(s) for upload`);
  }

  return (
    <AppShell>
      <Card>
        <CardHeader>
          <CardTitle>Upload Dataset Assets</CardTitle>
        </CardHeader>
        <CardContent>
          <input type="file" multiple onChange={onChange} />
          <div className="mt-3">
            <Button onClick={onUpload} disabled={files.length === 0}>Upload</Button>
          </div>
          {msg ? <Alert variant="info" className="mt-3">{msg}</Alert> : null}
        </CardContent>
      </Card>
    </AppShell>
  );
}
