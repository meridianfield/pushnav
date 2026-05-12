import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SkyDome } from "@/components/live-view/SkyDome";
import type { EnginePayload } from "@/lib/types";
import { SetupStep } from "./SetupStep";
import { SyncStep } from "./SyncStep";
import { SyncConfirmStep } from "./SyncConfirmStep";
import { CalibrateStep } from "./CalibrateStep";
import { WarmingUpStep } from "./WarmingUpStep";
import { TrackingStep } from "./TrackingStep";

interface Props {
  state: EnginePayload;
}

function StepCard({ state }: Props) {
  switch (state.state) {
    case "SETUP":        return <SetupStep state={state} />;
    case "SYNC":         return <SyncStep state={state} />;
    case "SYNC_CONFIRM": return <SyncConfirmStep state={state} />;
    case "CALIBRATE":    return <CalibrateStep state={state} />;
    case "WARMING_UP":   return <WarmingUpStep state={state} />;
    case "TRACKING":     return <TrackingStep state={state} />;
    case "RECONNECTING": return <Card className="flex flex-col"><CardContent className="p-4">Reconnecting to camera…</CardContent></Card>;
    case "ERROR":        return <Card className="flex flex-col"><CardContent className="p-4 text-destructive">Error — restart required</CardContent></Card>;
    default:             return null;
  }
}

export function Wizard({ state }: Props) {
  const p = state.pointing;
  const nav = state.nav;
  return (
    <div className="grid md:grid-cols-2 gap-2 items-stretch h-full">
      <StepCard state={state} />

      <Card className="flex flex-col">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Sky View</CardTitle>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <span
                  className="inline-block w-1.5 h-1.5 rounded-full"
                  style={{ background: "#ffd460" }}
                />
                Pointing
              </span>
              <span className="inline-flex items-center gap-1">
                <span
                  className="inline-block w-1.5 h-1.5 rounded-full"
                  style={{ background: "var(--primary-foreground)" }}
                />
                Target
              </span>
            </div>
          </div>
        </CardHeader>
        <CardContent className="flex-1 min-h-0 pb-3">
          <SkyDome
            pointingRaDeg={p.valid ? p.ra_deg : null}
            pointingDecDeg={p.valid ? p.dec_deg : null}
            targetRaDeg={nav?.active ? nav.target_ra_deg : null}
            targetDecDeg={nav?.active ? nav.target_dec_deg : null}
            targetLabel={nav?.target_name ?? null}
            latDeg={state.location.latitude}
            lonDeg={state.location.longitude}
            astroNowIso={state.astro_now_iso}
          />
        </CardContent>
      </Card>
    </div>
  );
}
