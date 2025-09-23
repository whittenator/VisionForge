import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';
import Alert from '@/components/ui/Alert';
import ErrorState from '@/components/common/ErrorState';
import { apiPost } from '@/services/api';

interface Project {
  id: string;
  name: string;
  description?: string;
}

export default function ProjectsCreate() {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [created, setCreated] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name) {
      setError('Project name is required');
      return;
    }
    
    setError(null);
    setLoading(true);
    
    try {
      const project = await apiPost<Project>('/api/projects', { 
        name, 
        description: description || undefined 
      });
      setCreated(`Created project ${name}`);
      setTimeout(() => navigate(`/projects/${project.id}`), 400);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create project');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>New Project</CardTitle>
      </CardHeader>
      <CardContent>
      <form onSubmit={onSubmit} className="space-y-3">
        <label className="block text-sm font-medium">
          Name
          <Input 
            value={name} 
            onChange={(e) => setName(e.target.value)} 
            placeholder="My Project" 
            disabled={loading}
          />
        </label>
        <label className="block text-sm font-medium">
          Description (optional)
          <Input 
            value={description} 
            onChange={(e) => setDescription(e.target.value)} 
            placeholder="A brief description of the project" 
            disabled={loading}
          />
        </label>
        <Button type="submit" disabled={loading}>
          {loading ? 'Creating...' : 'Create'}
        </Button>
      </form>
{error ? <div className="mt-3"><ErrorState title="Error" description={error} /></div> : null}
{created ? <Alert variant="success" className="mt-3">{created}</Alert> : null}
      </CardContent>
    </Card>
  );
}
