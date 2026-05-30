import React, { useState } from 'react';
import ImageUploader from '@/components/datasets/ImageUploader';
import ArchiveImporter, { type ImportResult } from '@/components/datasets/ArchiveImporter';

type Tab = 'upload' | 'import';

interface DataSourcePanelProps {
  datasetId: string;
  /** Open (unlocked) version that new data should land in. */
  versionId: string;
  onUploaded?: (count: number) => void;
  onImported?: (result: ImportResult) => void;
}

/**
 * Tabbed data-entry surface: upload new imagery or import a labeled archive.
 * Shared by the dataset creation wizard (step 2) and the detail "Data" tab.
 */
export default function DataSourcePanel({
  datasetId,
  versionId,
  onUploaded,
  onImported,
}: DataSourcePanelProps) {
  const [tab, setTab] = useState<Tab>('upload');

  const tabBtn = (id: Tab, label: string) => {
    const active = tab === id;
    return (
      <button
        key={id}
        type="button"
        onClick={() => setTab(id)}
        aria-pressed={active}
        className={[
          'h-8 px-3 font-mono text-[0.6875rem] tracking-wide border-b-2 transition-colors',
          active
            ? 'border-[var(--hud-accent)] text-[var(--hud-text-primary)]'
            : 'border-transparent text-[var(--hud-text-muted)] hover:text-[var(--hud-text-secondary)]',
        ].join(' ')}
      >
        {label}
      </button>
    );
  };

  return (
    <div className="border border-[var(--hud-border-default)] bg-[var(--hud-surface)]">
      <div className="flex items-center gap-1 border-b border-[var(--hud-border-subtle)] px-2">
        {tabBtn('upload', 'UPLOAD IMAGES')}
        {tabBtn('import', 'IMPORT LABELED ARCHIVE')}
      </div>
      <div className="p-4">
        {tab === 'upload' ? (
          <ImageUploader datasetId={datasetId} versionId={versionId} onComplete={onUploaded} />
        ) : (
          <ArchiveImporter datasetId={datasetId} versionId={versionId} onComplete={onImported} />
        )}
      </div>
    </div>
  );
}
