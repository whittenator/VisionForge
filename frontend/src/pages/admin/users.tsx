import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Badge from '@/components/ui/Badge';
import Alert from '@/components/ui/Alert';
import Loading from '@/components/common/Loading';
import EmptyState from '@/components/common/EmptyState';
import { apiGet, apiPost } from '@/services/api';

interface Workspace {
  id: string;
  name: string;
}

interface Member {
  id: string;
  user_id: string;
  email?: string;
  username?: string;
  role: string;
  joined_at?: string;
}

const ROLES = ['viewer', 'annotator', 'developer', 'admin', 'owner'];

function roleVariant(role: string): 'default' | 'success' | 'warning' | 'danger' {
  switch (role) {
    case 'owner': return 'danger';
    case 'admin': return 'warning';
    case 'developer': return 'success';
    default: return 'default';
  }
}

export default function AdminUsers() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<string>('');
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [membersLoading, setMembersLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Invite form state
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('annotator');
  const [inviteMsg, setInviteMsg] = useState<string | null>(null);
  const [inviting, setInviting] = useState(false);

  useEffect(() => {
    apiGet<Workspace[]>('/api/workspaces')
      .then((ws) => {
        setWorkspaces(ws);
        if (ws.length > 0) {
          setSelectedWorkspace(ws[0].id);
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load workspaces'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedWorkspace) return;
    setMembersLoading(true);
    apiGet<Member[]>(`/api/workspaces/${selectedWorkspace}/members`)
      .then(setMembers)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load members'))
      .finally(() => setMembersLoading(false));
  }, [selectedWorkspace]);

  async function handleInviteSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedWorkspace || !inviteEmail) return;
    setInviting(true);
    setInviteMsg(null);
    try {
      await apiPost(`/api/workspaces/${selectedWorkspace}/invite`, {
        email: inviteEmail,
        role: inviteRole,
      });
      setInviteMsg(`Successfully invited ${inviteEmail} as ${inviteRole}`);
      setInviteEmail('');
      const data = await apiGet<Member[]>(`/api/workspaces/${selectedWorkspace}/members`);
      setMembers(Array.isArray(data) ? data : []);
    } catch (err) {
      setInviteMsg(err instanceof Error ? err.message : 'Failed to invite user');
    } finally {
      setInviting(false);
    }
  }

  const currentWorkspace = workspaces.find((w) => w.id === selectedWorkspace);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Admin: Users & Members</h1>

      {error && <Alert variant="error">{error}</Alert>}

      {/* Workspace selector */}
      {workspaces.length > 1 && (
        <div className="flex items-center gap-3">
          <label htmlFor="workspace-select" className="text-sm font-medium">Workspace</label>
          <Select
            id="workspace-select"
            value={selectedWorkspace}
            onChange={(e) => setSelectedWorkspace(e.target.value)}
            className="max-w-xs"
          >
            {workspaces.map((w) => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </Select>
        </div>
      )}

      {loading ? (
        <Loading label="Loading workspaces…" />
      ) : (
        <>
          {/* Members list */}
          <Card>
            <CardHeader>
              <CardTitle>
                {currentWorkspace ? `${currentWorkspace.name} — Members` : 'Workspace Members'}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {membersLoading ? (
                <Loading label="Loading members…" />
              ) : members.length === 0 ? (
                <EmptyState
                  title="No members yet"
                  description="Invite people to collaborate in this workspace."
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm" aria-label="Members list">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground">
                        <th className="pb-2 pr-4 font-medium">User</th>
                        <th className="pb-2 pr-4 font-medium">Role</th>
                        {members.some((m) => m.joined_at) && (
                          <th className="pb-2 font-medium">Joined</th>
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {members.map((m) => (
                        <tr key={m.id} data-testid="user-row" className="border-b last:border-0">
                          <td className="py-2 pr-4">
                            <div data-testid="user-email" className="font-medium">
                              {m.email || m.username || m.user_id.slice(0, 12)}
                            </div>
                            {m.email && m.username && (
                              <div className="text-xs text-muted-foreground">{m.username}</div>
                            )}
                          </td>
                          <td className="py-2 pr-4">
                            <Badge
                              data-testid="user-role"
                              variant={roleVariant(m.role)}
                            >
                              {m.role}
                            </Badge>
                          </td>
                          {m.joined_at && (
                            <td className="py-2 text-muted-foreground">
                              {new Date(m.joined_at).toLocaleDateString()}
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Invite form */}
          <Card>
            <CardHeader>
              <CardTitle>Invite Member</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-4">
                Invite a new member to the workspace by email.
              </p>
              <form onSubmit={handleInviteSubmit} className="flex flex-wrap items-end gap-3" aria-label="Create user form">
                <div className="space-y-1 flex-1 min-w-[200px]">
                  <label htmlFor="invite-email" className="block text-xs text-muted-foreground">Email</label>
                  <Input
                    id="invite-email"
                    aria-label="Email"
                    type="email"
                    placeholder="colleague@example.com"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <label htmlFor="invite-role" className="block text-xs text-muted-foreground">Role</label>
                  <Select
                    id="invite-role"
                    aria-label="Role"
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value)}
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r.charAt(0).toUpperCase() + r.slice(1)}
                      </option>
                    ))}
                  </Select>
                </div>
                <Button aria-label="Create user" type="submit" disabled={inviting}>
                  {inviting ? 'Sending…' : 'Send Invite'}
                </Button>
              </form>
              {inviteMsg && (
                <Alert variant="info" className="mt-3">{inviteMsg}</Alert>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
