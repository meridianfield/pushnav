import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { EnginePayload } from "@/lib/types";

interface Props {
  state: EnginePayload;
}

function formatRa(deg: number): string {
  const ra_h = deg / 15;
  const h = Math.floor(ra_h);
  const m = Math.floor((ra_h - h) * 60);
  const s = ((ra_h - h - m / 60) * 3600).toFixed(2);
  return `${h}h ${m.toString().padStart(2, "0")}m ${s.padStart(5, "0")}s`;
}

function formatDec(deg: number): string {
  const sign = deg >= 0 ? "+" : "-";
  const abs = Math.abs(deg);
  const d = Math.floor(abs);
  const m = Math.floor((abs - d) * 60);
  const s = ((abs - d - m / 60) * 3600).toFixed(1);
  return `${sign}${d}° ${m.toString().padStart(2, "0")}' ${s}"`;
}

export function PlateSolveStats({ state }: Props) {
  if (!["CALIBRATE", "WARMING_UP", "TRACKING"].includes(state.state)) {
    return null;
  }
  const p = state.pointing;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base text-primary">Plate-Solve Stats</CardTitle>
      </CardHeader>
      <CardContent className="text-xs space-y-1 font-mono">
        <div>RA:&nbsp;&nbsp;<span className="text-muted-foreground">{p.valid ? formatRa(p.ra_deg) : "--"}</span></div>
        <div>Dec: <span className="text-muted-foreground">{p.valid ? formatDec(p.dec_deg) : "--"}</span></div>
        <div>Roll: <span className="text-muted-foreground">{p.valid ? `${p.roll_deg.toFixed(1)}°` : "--"}</span></div>
        <div className="pt-1 border-t border-border" />
        <div>Matches: <span className="text-muted-foreground">{p.valid ? p.matches : "--"}</span></div>
        <div>Prob: <span className="text-muted-foreground">{p.valid ? p.prob.toExponential(1) : "--"}</span></div>
        <div>Last solve: <span className="text-muted-foreground">{p.solve_age_s !== null ? `${p.solve_age_s.toFixed(1)}s ago` : "--"}</span></div>
        <div>Failures: <span className="text-muted-foreground">{state.failures}</span></div>
      </CardContent>
    </Card>
  );
}
