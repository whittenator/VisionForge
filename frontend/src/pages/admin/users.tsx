import React, { useState, useEffect } from 'react';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Badge from '@/components/ui/Badge';
import Alert from '@/components/ui/Alert';
import Loading from '@/components/common/Loading';
import EmptyState from '@/components/common/EmptyState';
import { apiGet } from '@/services/api';

interface Workspace { id: string; name: string; }
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
    case 'owner':     return 'danger';
    case 'admin':     return 'warning';
    case 'developer': return 'success';
    default:          return 'default';
  }
}

export default function AdminUsers() {
  const [workspaces, setWorkspaces]           = useState<Workspace[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<string>('');
  const [members, setMembers]                 = useState<Member[]>([]);
  const [loading, setLoading]                 = useState(true);
  const [membersLoading, setMembersLoading]   = useState(false);
  const [error, setError]                     = useState<string | null>(null);
  const [inviteEmail, setInviteEmail]         = useState('');
  const [inviteRole, setInviteRole]           = useState('annotator');
  const [inviteMsg, setInviteMsg]             = useState<string | null>(null);

  useEffect(() => {
    apiGet<Workspace[]>('/api/workspaces')
      .then((ws) => {
        setWorkspaces(ws);
        if (ws.length > 0) setSelectedWorkspace(ws[0].id);
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

  function handleInviteSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!inviteEmail) return;
    setInviteMsg(`Invitation for ${inviteEmail} (${inviteRole}) would be sent. Invite endpoint not yet implemented.`);
    setInviteEmail('');
    setInviteRole('annotator');
  }

  const currentWorkspace = workspaces.find((w) => w.id === selectedWorkspace);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="border-b border-[var(--hud-border-subtle)] pb-3">
        <div className="label-overline mb-0.5">// Admin / Users</div>
        <h1>Workspace Members</h1>
      </div>

      {error && <Alert variant="error">{error}</Alert>}

      {/* Workspace selector */}
      {workspaces.length > 1 && (
        <div className="flex items-center gap-3">
          <label htmlFor="workspace-select" className="label-overline whitespace-nowrap">Workspace</label>
          <Select
            id="workspace-select"
            value={selectedWorkspace}
            onChange={(e) => setSelectedWorkspace(e.target.value)}
            className="max-w-xs"
          >
            {workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </Select>
        </div>
      )}

      {loading ? (
        <div className="py-6"><Loading label="Loading workspaces…" /></div>
      ) : (
        <>
          {/* Members table */}
          <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
            <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center gap-2">
              <div className="h-1.5 w-1.5 bg-[var(--hud-accent)]" />
              <span className="label-overline">
                {currentWorkspace ? `${currentWorkspace.name} — Members` : 'Workspace Members'}
              </span>
            </div>

            {membersLoading ? (
              <div className="px-4 py-4"><Loading label="Loading members…" /></div>
            ) : members.length === 0 ? (
              <div className="px-4 py-4">
                <EmptyState title="No members" description="Invite people to collaborate in this workspace." />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm" aria-label="Members list">
                  <thead>
                    <tr className="border-b border-[var(--hud-border-subtle)] bg-[var(--hud-inset)]">
                      <th className="px-4 py-2 text-left label-overline">User</th>
                      <th className="px-4 py-2 text-left label-overline">Role</th>
                      {members.some((m) => m.joined_at) && (
                        <th className="px-4 py-2 text-left label-overline">Joined</th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {members.map((m) => (
                      <tr
                        key={m.id}
                        data-testid="user-row"
                        className="border-b border-[var(--hud-border-subtle)] last:border-0 hover:bg-[var(--hud-elevated)] transition-colors"
                      >
                        <td className="px-4 py-2">
                          <div data-testid="user-email" className="font-medium text-[var(--hud-text-primary)] text-xs">
                            {m.email || m.username || m.user_id.slice(0, 12)}
                          </div>
                          {m.email && m.username && (
                            <div className="text-[0.6875rem] font-mono text-[var(--hud-text-muted)]">{m.username}</div>
                          )}
                        </td>
                        <td className="px-4 py-2">
                          <Badge data-testid="user-role" variant={roleVariant(m.role)}>{m.role}</Badge>
                        </td>
                        {m.joined_at && (
                          <td className="px-4 py-2 text-xs font-mono text-[var(--hud-text-muted)]">
                            {new Date(m.joined_at).toLocaleDateString()}
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Invite form */}
          <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
            <div className="border-b border-[var(--hud-border-subtle)] px-4 py-2 flex items-center gap-2">
              <div className="h-1.5 w-1.5 bg-[var(--hud-border-strong)]" />
              <span className="label-overline">Invite Member</span>
            </div>
            <div className="p-4">
              <p className="text-xs text-[var(--hud-text-muted)] mb-4">
                Invite a new member to the workspace by email.
              </p>
              <form
                onSubmit={handleInviteSubmit}
                className="flex flex-wrap items-end gap-3"
                aria-label="Create user form"
              >
                <div className="space-y-1 flex-1 min-w-[200px]">
                  <label htmlFor="invite-email" className="label-overline block">Email</label>
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
                  <label htmlFor="invite-role" className="label-overline block">Role</label>
                  <Select
                    id="invite-role"
                    aria-label="Role"
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value)}
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
                    ))}
                  </Select>
                </div>
                <Button aria-label="Create user" type="submit">Send Invite</Button>
              </form>
              {inviteMsg && <Alert variant="info" className="mt-3">{inviteMsg}</Alert>}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
