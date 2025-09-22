import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AppShell from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';

export default function ExperimentsNew() {
  const [name, setName] = useState('');
  const [msg, setMsg] = useState<string | null>(null);
  const navigate = useNavigate();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name) return;
    setMsg(`Enqueued training run '${name}'`);
    setTimeout(() => navigate('/experiments'), 400);
  }

  return (
    <AppShell>
      <Card>
        <CardHeader><CardTitle>New Training Run</CardTitle></CardHeader>
        <CardContent>
        <form onSubmit={submit} className="space-y-3">
          <label className="block text-sm font-medium">
            Name
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Baseline" />
          </label>
          <Button type="submit">Launch</Button>
        </form>
        {msg ? <Alert variant="success" className="mt-3">{msg}</Alert> : null}
        </CardContent>
      </Card>
    </AppShell>
  );
}
