import React, { useState } from 'react';
import AppShell from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import { Link } from 'react-router-dom';

type Artifact = { id: string; name: string; type: 'model' | 'dataset' };

export default function ArtifactsIndex() {
  const [artifacts] = useState<Artifact[]>([
    { id: 'a1', name: 'Model v1', type: 'model' },
  ]);
  return (
    <AppShell>
      <h2 className="text-xl font-semibold">Artifacts</h2>
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {artifacts.map((a) => (
          <Card key={a.id}>
            <CardHeader><CardTitle>{a.name}</CardTitle></CardHeader>
            <CardContent>
              <Badge className="mr-2">{a.type}</Badge>
              <Link className="text-blue-700 underline" to={`/artifacts/export?id=${a.id}`}>Export ONNX</Link>
            </CardContent>
          </Card>
        ))}
      </div>
    </AppShell>
  );
}
