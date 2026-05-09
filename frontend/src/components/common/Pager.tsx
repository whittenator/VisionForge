import React from 'react';
import Button from '@/components/ui/Button';

interface Props {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}

export default function Pager({ page, pageSize, total, onChange }: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (totalPages <= 1) return null;
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(total, page * pageSize);
  return (
    <div className="flex items-center justify-between text-xs font-mono text-[var(--hud-text-muted)] pt-2">
      <span>
        SHOWING <span className="text-[var(--hud-text-data)]">{start}</span>—
        <span className="text-[var(--hud-text-data)]">{end}</span> OF{' '}
        <span className="text-[var(--hud-text-data)]">{total}</span>
      </span>
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          ← PREV
        </Button>
        <span>
          PAGE <span className="text-[var(--hud-text-data)]">{page}</span> /{' '}
          <span className="text-[var(--hud-text-data)]">{totalPages}</span>
        </span>
        <Button
          size="sm"
          variant="outline"
          disabled={page >= totalPages}
          onClick={() => onChange(page + 1)}
        >
          NEXT →
        </Button>
      </div>
    </div>
  );
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
