// Mirrors the schema produced by scripts/sync_catalog.py.
// Keep this file in sync with that script's build_entry() output.

export type ObjectType =
  | "cluster"
  | "nebula"
  | "galaxy"
  | "star"
  | "asterism"
  | "planet"
  | "moon";

export type Difficulty = "beginner" | "intermediate";
export type VisualReward = "high" | "moderate" | "low";
export type LpTolerance = "high" | "medium" | "low";
export type Equipment =
  | "naked-eye"
  | "binoculars"
  | "small-telescope"
  | "medium-telescope"
  | "large-telescope";

export interface CatalogObject {
  id: string;                       // filename without .md
  name: string;
  designation: string;
  type: ObjectType;
  subtype?: string;
  constellation: string;
  magnitude?: number;
  distance?: string;
  bestViewing?: string;
  difficulty: Difficulty;
  visualReward: VisualReward;
  lpTolerance: LpTolerance;
  minEquipment: Equipment;
  rightAscension: string;            // "05h 35m 17.3s"
  declination: string;               // "-05° 23' 28\""
  description: string;
}

// Compass label for an azimuth in degrees (0=N, 90=E, 180=S, 270=W).
const COMPASS_POINTS = [
  "N", "NNE", "NE", "ENE",
  "E", "ESE", "SE", "SSE",
  "S", "SSW", "SW", "WSW",
  "W", "WNW", "NW", "NNW",
];
export function azimuthCompass(azDeg: number): string {
  const idx = Math.round(((azDeg % 360) + 360) / 22.5) % 16;
  return COMPASS_POINTS[idx];
}
