import { useCallback, useEffect, useState } from 'react';
import { apiGet, apiPost } from '@/services/api';
import type { Suggestion, SuggestModel } from './types';

interface SuggestResponse {
  artifact: { id: string; name: string; version: string };
  suggestions: {
    type: Suggestion['type'];
    geometry: Suggestion['geometry'];
    class_name: string;
    score: number;
  }[];
}

interface UseSuggestionsResult {
  models: SuggestModel[];
  selectedModelId: string;
  setSelectedModelId: (id: string) => void;
  suggestions: Suggestion[];
  setSuggestions: React.Dispatch<React.SetStateAction<Suggestion[]>>;
  loading: boolean;
  error: string | null;
  hasModel: boolean;
  fetchSuggestions: (assetId: string) => Promise<number>;
  clear: () => void;
}

/**
 * Loads the models trained on a dataset (newest first, auto-selecting the
 * latest) and fetches one-click annotation suggestions for an asset. Returned
 * suggestions are kept separate from committed annotations until accepted.
 */
export function useSuggestions(datasetId: string | undefined): UseSuggestionsResult {
  const [models, setModels] = useState<SuggestModel[]>([]);
  const [selectedModelId, setSelectedModelId] = useState('');
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!datasetId) return;
    let cancelled = false;
    apiGet<{ items: SuggestModel[] }>(`/api/annotations/suggest/artifacts?dataset_id=${datasetId}`)
      .then((d) => {
        if (cancelled) return;
        const items = d.items || [];
        setModels(items);
        if (items.length > 0) setSelectedModelId(items[0].id);
      })
      .catch(() => {
        if (!cancelled) setModels([]);
      });
    return () => {
      cancelled = true;
    };
  }, [datasetId]);

  const fetchSuggestions = useCallback(
    async (assetId: string): Promise<number> => {
      setLoading(true);
      setError(null);
      try {
        const res = await apiPost<SuggestResponse>('/api/annotations/suggest', {
          asset_id: assetId,
          artifact_id: selectedModelId || undefined,
        });
        const mapped: Suggestion[] = res.suggestions.map((s, i) => ({
          tempId: `sug-${Date.now()}-${i}`,
          type: s.type,
          class_name: s.class_name,
          geometry: s.geometry,
          score: s.score,
        }));
        setSuggestions(mapped);
        return mapped.length;
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Suggestion failed';
        setError(msg);
        throw new Error(msg);
      } finally {
        setLoading(false);
      }
    },
    [selectedModelId],
  );

  const clear = useCallback(() => setSuggestions([]), []);

  return {
    models,
    selectedModelId,
    setSelectedModelId,
    suggestions,
    setSuggestions,
    loading,
    error,
    hasModel: models.length > 0,
    fetchSuggestions,
    clear,
  };
}
