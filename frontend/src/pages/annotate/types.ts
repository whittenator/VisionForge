// Shared types for the annotator.

export type AnnotationType = 'box' | 'polygon' | 'keypoint' | 'classification';
export type Mode = AnnotationType | 'select';

export interface Point {
  x: number;
  y: number;
}

export interface BoxGeometry {
  x: number;
  y: number;
  w: number;
  h: number;
}
export interface PointsGeometry {
  points: Point[];
}
export interface ClassGeometry {
  class: string;
}
export type Geometry = BoxGeometry | PointsGeometry | ClassGeometry;

export interface Annotation {
  id: string | null;
  type: AnnotationType;
  class_name: string;
  geometry: Geometry;
  version: number;
  isNew: boolean;
  dirty: boolean;
  /** Marks annotations that originated from an accepted model suggestion. */
  origin?: 'manual' | 'suggested';
}

export interface Suggestion {
  /** Stable client-side id, e.g. `sug-3`. */
  tempId: string;
  type: AnnotationType;
  class_name: string;
  geometry: Geometry;
  score: number;
}

export interface SuggestModel {
  id: string;
  name: string;
  version: string;
  format?: string | null;
  created_at?: string | null;
}

export interface NeighborInfo {
  prev: string | null;
  next: string | null;
  index: number | null;
  total: number;
}
