import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { EnginePayload } from "@/lib/types";

function formatRa(deg: number): string {
  const ra_h = deg / 15;
  const h = Math.floor(ra_h);
  const m = Math.floor((ra_h - h) * 60);
  const s = ((ra_h - h - m / 60) * 3600).toFixed(1);
  return `${h}h ${m.toString().padStart(2, "0")}m ${s}s`;
}

function formatDec(deg: number): string {
  const sign = deg >= 0 ? "+" : "-";
  const abs = Math.abs(deg);
  const d = Math.floor(abs);
  const m = Math.floor((abs - d) * 60);
  const s = ((abs - d - m / 60) * 3600).toFixed(0);
  return `${sign}${d}° ${m.toString().padStart(2, "0")}' ${s}"`;
}

export function GotoTargetBanner({ state }: { state: EnginePayload }) {
  const nav = state.nav;
  if (!nav?.active) return null;

  const name = nav.target_name ?? "Manual target";
  const sep = nav.separation_deg;
  const dir = nav.direction_text;
  const inFov = nav.in_fov;

  return (
    <div className="flex items-center gap-3 rounded-md border border-border bg-card text-card-foreground px-4 py-2 mb-3 text-sm">
      <Badge variant={inFov ? "default" : "secondary"}>
        {inFov ? "IN FOV" : "PUSH"}
      </Badge>
      <div className="flex-1 min-w-0">
        <div className="font-semibold truncate">
          Target: {name}
        </div>
        <div className="text-xs text-muted-foreground font-mono truncate">
          {formatRa(nav.target_ra_deg)} · {formatDec(nav.target_dec_deg)}
          {sep !== null && (
            <>
              {" · "}
              {sep < 1 ? `${(sep * 60).toFixed(1)}'` : `${sep.toFixed(2)}°`} {dir}
            </>
          )}
        </div>
      </div>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => api.clearGoto()}
      >
        Clear
      </Button>
    </div>
  );
}
