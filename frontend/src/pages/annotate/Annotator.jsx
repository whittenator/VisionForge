import React, { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';

// Minimal annotator that supports keyboard-first actions:
// - ArrowLeft/ArrowRight: navigate assets (simulated)
// - Key 'b': toggle bounding box mode
// - Key 'c': toggle classification tag 'cat'
// - Enter: save (sets aria-live status)
// - Shows current state for Playwright to assert
export default function AnnotatorPage() {
  const { assetId } = useParams();
  const [mode, setMode] = useState('none');
  const [tagCat, setTagCat] = useState(false);
  const [status, setStatus] = useState('Idle');
  const containerRef = useRef(null);

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'b') {
        setMode((m) => (m === 'box' ? 'none' : 'box'));
      } else if (e.key === 'c') {
        setTagCat((v) => !v);
      } else if (e.key === 'Enter') {
        setStatus('Saved');
      } else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        setStatus(`Navigated ${e.key === 'ArrowRight' ? 'next' : 'prev'}`);
      }
    }
    const node = containerRef.current;
    node?.addEventListener('keydown', onKeyDown);
    return () => node?.removeEventListener('keydown', onKeyDown);
  }, []);

  return (
    <div
      ref={containerRef}
      tabIndex={0}
      role="application"
      aria-label="Annotator"
      className="border rounded p-4 outline-none"
      data-testid="annotator-container"
    >
      <div className="mb-2">
        <span>Asset ID: </span>
        <span data-testid="asset-id">{assetId}</span>
      </div>
      <div className="space-x-2 mb-2">
        <span>Mode:</span>
        <span data-testid="mode">{mode}</span>
      </div>
      <div className="space-x-2 mb-2">
        <label>
          <input
            type="checkbox"
            checked={tagCat}
            onChange={() => setTagCat((v) => !v)}
            aria-label="Tag: cat"
          />
          <span className="ml-1">Tag: cat</span>
        </label>
        <span data-testid="tag-cat">{tagCat ? 'on' : 'off'}</span>
      </div>
      <div aria-live="polite" data-testid="status">
        {status}
      </div>
      <p className="text-sm text-gray-600 mt-3">
        Keyboard: b = box mode, c = toggle cat tag, Enter = save, arrows = navigate. Click here or press Tab to focus.
      </p>
    </div>
  );
}
