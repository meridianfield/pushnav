// Mirror of webserver/_build_payload — keep in sync by hand.

export type EngineState =
  | "SETUP"
  | "SYNC"
  | "SYNC_CONFIRM"
  | "CALIBRATE"
  | "WARMING_UP"
  | "TRACKING"
  | "RECONNECTING"
  | "ERROR";

export interface PointingData {
  valid: boolean;
  ra_deg: number;
  dec_deg: number;
  roll_deg: number;
  matches: number;
  prob: number;
  solve_age_s: number | null;
}

export interface NavData {
  active: boolean;
  target_name: string | null;
  target_ra_deg: number;
  target_dec_deg: number;
  separation_deg: number | null;
  direction_text: string;
  in_fov: boolean;
  pixel_x: number | null;
  pixel_y: number | null;
  camera_angle_deg: number | null;
  edge_x: number | null;
  edge_y: number | null;
  edge_angle_deg: number | null;
}

export interface ControlDescriptor {
  id?: string;     // server uses "id"
  name?: string;   // some payloads use "name"
  label: string;
  min: number;
  max: number;
  step: number;
  cur: number;     // current value — DPG protocol uses "cur"
  value?: number;  // legacy alias kept for back-compat
  unit?: string;
  type?: string;
}

export interface SyncCandidate {
  idx: number;
  name: string;
  ra_deg: number;
  dec_deg: number;
  magnitude: number;
  pixel_x: number;
  pixel_y: number;
}

export interface SyncBlock {
  in_progress: boolean;
  candidates: SyncCandidate[];
  selected_idx: number | null;
  error: string | null;
}

export interface ObserverLocation {
  name?: string;
  country?: string;
  latitude?: number;
  longitude?: number;
}

export interface ActivityLine {
  active: boolean;
  address: string | null;
  status?: unknown;
  object?: { name?: string; "localized-name"?: string } | null;
  location?: ObserverLocation | null;
}

export interface CameraBlock {
  connected: boolean;
  all_centroids: number[][] | null;     // [[y, x], ...]
  matched_centroids: number[][] | null; // [[y, x], ...]
}

export interface EnginePayload {
  state: EngineState;
  failures: number;
  pointing: PointingData;
  nav: NavData | null;
  origin_x: number;
  origin_y: number;
  image_w: number;
  image_h: number;
  finder_rotation: number;
  fov_h_deg: number;
  has_calibration: boolean;
  image_size: [number, number] | null;
  controls: ControlDescriptor[];
  sync: SyncBlock;
  stellarium: ActivityLine;
  lx200: ActivityLine;
  webserver: { url: string | null };
  audio_enabled: boolean;
  camera: CameraBlock;
  location: {
    latitude: number | null;
    longitude: number | null;
    source: "stellarium" | "manual" | null;
  };
  dev_mode: boolean;
  min_matches: number;
  max_prob: number;
  sample_active: string | null;
  // ISO UTC string when PUSHNAV_TESTDATE is in effect on the server,
  // null otherwise. Frontend treats null as "use real Date()", so an
  // unset env var is a true no-op.
  astro_now_iso: string | null;
}
