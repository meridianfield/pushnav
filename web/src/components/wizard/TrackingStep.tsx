import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { EnginePayload } from "@/lib/types";

function mountDeltas(
  navPxX: number,
  navPxY: number,
  originX: number,
  originY: number,
  fovHDeg: number,
  imgW: number,
  finderRotationDeg: number,
): { right: number; up: number } {
  // Pixels-per-degree in the camera image
  const scale = imgW / (2 * Math.tan((fovHDeg / 2) * (Math.PI / 180)));
  const dx = (navPxX - originX) / scale; // image-frame right = positive deg
  const dy = (originY - navPxY) / scale; // image-frame up = positive deg
  // Rotate by -finderRotation to get mount frame
  const phi = -finderRotationDeg * (Math.PI / 180);
  const right = dx * Math.cos(phi) - dy * Math.sin(phi);
  const up = dx * Math.sin(phi) + dy * Math.cos(phi);
  return { right, up };
}

function MountDeltaLine({ state }: { state: EnginePayload }) {
  const p = state.pointing;
  const nav = state.nav;
  if (!nav || nav.pixel_x === null || nav.pixel_y === null || !p.valid) {
    return null;
  }
  const m = mountDeltas(
    nav.pixel_x, nav.pixel_y,
    state.origin_x, state.origin_y,
    state.fov_h_deg, state.image_w, state.finder_rotation,
  );
  const rightLabel = m.right >= 0 ? "Right" : "Left";
  const upLabel = m.up >= 0 ? "Up" : "Down";
  return (
    <div className="text-xs font-mono text-muted-foreground">
      Dist: {nav.separation_deg?.toFixed(2)}°
      {" · "}{rightLabel} {Math.abs(m.right).toFixed(2)}°
      {" · "}{upLabel} {Math.abs(m.up).toFixed(2)}°
    </div>
  );
}

export function TrackingStep({ state }: { state: EnginePayload }) {
  const p = state.pointing;
  const nav = state.nav;
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Tracking</CardTitle>
          <Badge variant={p.valid ? "default" : "destructive"}>
            {p.valid ? "LOCK" : "LOST"}
          </Badge>
        </div>
        <CardDescription>
          {p.valid
            ? `RA ${p.ra_deg.toFixed(2)}° / Dec ${p.dec_deg.toFixed(2)}° / age ${p.solve_age_s}s`
            : "Acquiring stars…"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {nav?.active && (
          <div className="space-y-1">
            <div>
              Target: <strong>{nav.target_name ?? "—"}</strong>
              <Button variant="ghost" size="sm" onClick={() => api.clearGoto()} className="ml-2">
                Clear
              </Button>
            </div>
            <MountDeltaLine state={state} />
            {(!nav.in_fov || !p.valid) && nav.separation_deg !== null && (
              <div className="text-xs font-mono text-muted-foreground">
                {nav.direction_text} · {nav.separation_deg.toFixed(2)}°
              </div>
            )}
            <div className="text-[11px] text-muted-foreground">
              1° ~ 2 full moons wide
            </div>
          </div>
        )}
        <Button variant="outline" onClick={() => api.wizardAdvance()}>
          Stop tracking and restart setup
        </Button>
      </CardContent>
    </Card>
  );
}
