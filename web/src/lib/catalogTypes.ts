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
  magnitude: number | null;
  distance: string | null;
  bestViewing: string | null;
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

// Advanced catalog search types (Task 5+)
export interface NgcEntry {
  source: "ngc";
  id: string;
  aliases: string[];
  type: string;
  ra_deg: number;
  dec_deg: number;
  mag: number | null;
  constellation: string | null;
}

export interface StarEntry {
  source: "star";
  id: string;
  aliases: string[];
  ra_deg: number;
  dec_deg: number;
  mag: number | null;
  spectral: string | null;
  constellation: string | null;
}

export interface ManualEntry {
  source: "manual";
  ra_deg: number;
  dec_deg: number;
}

export type AdvancedEntry = NgcEntry | StarEntry | ManualEntry;

// Pretty label for an OpenNGC type code.
export const NGC_TYPE_LABELS: Record<string, string> = {
  G:   "Galaxy",
  GPair: "Galaxy pair",
  GTrpl: "Galaxy triple",
  GGroup: "Galaxy group",
  OC:  "Open cluster",
  GC:  "Globular cluster",
  Cl:  "Cluster",
  PN:  "Planetary nebula",
  HII: "HII region",
  EmN: "Emission nebula",
  RfN: "Reflection nebula",
  SNR: "Supernova remnant",
  Neb: "Nebula",
  Other: "Other",
};
