import React, { useState } from 'react';
import EmptyState from '@/components/common/EmptyState';

export default function AdminUsersPage() {
  const [users, setUsers] = useState([]);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('annotator');

  function addUser(e) {
    e.preventDefault();
    if (!email) return;
    setUsers((u) => [...u, { email, role }]);
    setEmail('');
    setRole('annotator');
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Admin: Users</h2>
      <form onSubmit={addUser} className="space-x-2" aria-label="Create user form">
        <input
          placeholder="email@example.com"
          aria-label="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="border rounded px-2 py-1"
        />
        <select
          aria-label="Role"
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="border rounded px-2 py-1"
        >
          <option value="annotator">Annotator</option>
          <option value="admin">Admin</option>
          <option value="viewer">Viewer</option>
        </select>
        <button type="submit" className="bg-blue-600 text-white px-3 py-1 rounded" aria-label="Create user">
          Create
        </button>
      </form>

      {users.length === 0 ? (
        <EmptyState title="No users" description="Invite your first user to collaborate." />
      ) : (
        <ul aria-label="Users list" className="list-disc pl-6">
          {users.map((u, i) => (
            <li key={i} data-testid="user-row">
              <span data-testid="user-email">{u.email}</span> — <span data-testid="user-role">{u.role}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
