export interface SkyMarker {
  altDeg: number;
  azDeg: number;
  color: string;
  label?: string;
  size?: number;
}

export interface ThemeColors {
  gridLines: string;
  gridLabels: string;
  horizon: string;
  ground: string;
  pointing: string;
  target: string;
  line: string;
}
