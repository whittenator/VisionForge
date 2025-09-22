import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AppShell from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';
import ErrorState from '@/components/common/ErrorState';

export default function ProjectsCreate() {
  const [name, setName] = useState('');
  const [created, setCreated] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name) {
      setError('Project name is required');
      return;
    }
    setError(null);
    const id = `p_${Date.now()}`;
    setCreated(`Created project ${name}`);
    setTimeout(() => navigate(`/projects/${id}`), 400);
  }

  return (
    <AppShell>
      <Card>
        <CardHeader>
          <CardTitle>New Project</CardTitle>
        </CardHeader>
        <CardContent>
        <form onSubmit={onSubmit} className="space-y-3">
          <label className="block text-sm font-medium">
            Name
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="My Project" />
          </label>
          <Button type="submit">Create</Button>
        </form>
  {error ? <div className="mt-3"><ErrorState title="Validation error" description={error} /></div> : null}
  {created ? <Alert variant="success" className="mt-3">{created}</Alert> : null}
        </CardContent>
      </Card>
    </AppShell>
  );
}
