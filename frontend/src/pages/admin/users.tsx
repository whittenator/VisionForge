import React, { useState } from 'react';
import AppShell from '@/components/layout/AppShell';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';

export default function AdminUsers() {
  const [users, setUsers] = useState<{ email: string; role: string }[]>([]);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('annotator');

  function addUser(e: React.FormEvent) {
    e.preventDefault();
    if (!email) return;
    setUsers((u) => [...u, { email, role }]);
    setEmail('');
    setRole('annotator');
  }

  return (
    <AppShell>
      <Card>
        <CardHeader>
          <CardTitle>Admin: Users</CardTitle>
        </CardHeader>
        <CardContent>
        <form onSubmit={addUser} className="flex flex-wrap items-center gap-2" aria-label="Create user form">
          <Input aria-label="Email" placeholder="email@example.com" value={email} onChange={(e) => setEmail(e.target.value)} />
          <Select aria-label="Role" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="annotator">Annotator</option>
            <option value="admin">Admin</option>
            <option value="viewer">Viewer</option>
          </Select>
          <Button aria-label="Create user" type="submit">Create</Button>
        </form>
        <ul className="mt-4 space-y-1" aria-label="Users list">
          {users.map((u, i) => (
            <li key={i} data-testid="user-row" className="text-sm text-gray-700">
              <span data-testid="user-email" className="font-medium">{u.email}</span>
              <span> — </span>
              <span data-testid="user-role" className="uppercase tracking-wide text-gray-500">{u.role}</span>
            </li>
          ))}
        </ul>
        </CardContent>
      </Card>
    </AppShell>
  );
}
