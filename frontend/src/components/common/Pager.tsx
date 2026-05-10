import React, { useEffect } from 'react';
import Button from '@/components/ui/Button';

interface Props {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}

export default function Pager({ page, pageSize, total, onChange }: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  // Clamp the caller's `page` to a valid range so a stale page from a prior
  // filter state never displays an impossible "26—10 of 10" range.
  const safePage = Math.min(Math.max(1, Math.floor(page) || 1), totalPages);

  // If the caller is out of bounds (filters reduced `total` but they still
  // hold the old page), surface a snap-back so the parent's state agrees.
  useEffect(() => {
    if (safePage !== page) onChange(safePage);
  }, [safePage, page, onChange]);

  if (totalPages <= 1) return null;
  const start = total === 0 ? 0 : (safePage - 1) * pageSize + 1;
  const end = Math.min(total, safePage * pageSize);
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
          disabled={safePage <= 1}
          onClick={() => onChange(Math.max(1, safePage - 1))}
        >
          ← PREV
        </Button>
        <span>
          PAGE <span className="text-[var(--hud-text-data)]">{safePage}</span> /{' '}
          <span className="text-[var(--hud-text-data)]">{totalPages}</span>
        </span>
        <Button
          size="sm"
          variant="outline"
          disabled={safePage >= totalPages}
          onClick={() => onChange(Math.min(totalPages, safePage + 1))}
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
