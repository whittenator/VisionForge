import React, { useState, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Spinner from '@/components/ui/Spinner';
import { apiGet, apiPut } from '@/services/api';

interface ALItem {
  id: string;
  asset_id: string;
  priority: number;
  resolved_status: string;
  resolved_at?: string;
  asset?: { id: string; uri: string; download_url?: string; label_status: string };
}

export default function ALRunDetail() {
  const { runId } = useParams<{ runId: string }>();
  const [items, setItems] = useState<ALItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'pending' | 'resolved'>('all');

  useEffect(() => {
    if (!runId) return;
    apiGet<ALItem[]>(`/api/al/runs/${runId}/items`)
      .then(data => setItems(Array.isArray(data) ? data : []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [runId]);

  async function resolveItem(itemId: string) {
    try {
      await apiPut(`/api/al/runs/${runId}/items/${itemId}/resolve`, { resolved_status: 'resolved' });
      setItems(prev => prev.map(i => i.id === itemId ? { ...i, resolved_status: 'resolved' } : i));
    } catch {}
  }

  const filtered = items.filter(i =>
    filter === 'all' ? true : filter === 'pending' ? i.resolved_status === 'pending' : i.resolved_status === 'resolved'
  );
  const pending = items.filter(i => i.resolved_status === 'pending').length;
  const resolved = items.filter(i => i.resolved_status === 'resolved').length;

  return (
    <div className="space-y-4">
      <div>
        <nav className="text-xs text-muted-foreground mb-1">
          <Link to="/al" className="hover:underline">Active Learning</Link>
          {' / '}
          <span>Run {runId?.slice(0, 8)}</span>
        </nav>
        <h1 className="text-2xl font-semibold">AL Run Items</h1>
      </div>

      <div className="flex gap-4">
        <div className="rounded-lg border p-3 text-center min-w-[80px]">
          <div className="text-2xl font-bold text-yellow-600">{pending}</div>
          <div className="text-xs text-muted-foreground">Pending</div>
        </div>
        <div className="rounded-lg border p-3 text-center min-w-[80px]">
          <div className="text-2xl font-bold text-green-600">{resolved}</div>
          <div className="text-xs text-muted-foreground">Resolved</div>
        </div>
        <div className="rounded-lg border p-3 text-center min-w-[80px]">
          <div className="text-2xl font-bold">{items.length}</div>
          <div className="text-xs text-muted-foreground">Total</div>
        </div>
      </div>

      <div className="flex gap-2">
        {(['all', 'pending', 'resolved'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded-full text-sm border ${filter === f ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : filtered.length === 0 ? (
        <p className="text-center py-8 text-muted-foreground">No items found</p>
      ) : (
        <div className="space-y-2">
          {filtered.map((item, idx) => (
            <div key={item.id} className="flex items-center gap-4 p-3 rounded-lg border hover:bg-muted/50">
              <div className="text-sm font-mono text-muted-foreground w-6 text-right">{idx + 1}</div>
              {item.asset?.download_url ? (
                <img src={item.asset.download_url} alt="" className="w-16 h-16 object-cover rounded border" />
              ) : (
                <div className="w-16 h-16 bg-slate-100 rounded border flex items-center justify-center text-xs text-muted-foreground">
                  {item.asset_id.slice(0, 6)}
                </div>
              )}
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium font-mono">{item.asset_id.slice(0, 12)}…</div>
                <div className="text-xs text-muted-foreground">
                  Priority: <span className="font-mono">{item.priority.toFixed(4)}</span>
                </div>
              </div>
              <Badge variant={item.resolved_status === 'resolved' ? 'success' : 'warning'}>
                {item.resolved_status}
              </Badge>
              <div className="flex gap-2">
                <Link to={`/annotate/${item.asset_id}`}>
                  <Button size="sm" variant="outline">Annotate</Button>
                </Link>
                {item.resolved_status === 'pending' && (
                  <Button size="sm" onClick={() => resolveItem(item.id)}>
                    Resolve
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
