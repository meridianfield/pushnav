import { Volume2, VolumeX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { EnginePayload } from "@/lib/types";

interface Props {
  state: EnginePayload;
}

const TRACKING_STATES = ["CALIBRATE", "WARMING_UP", "TRACKING"];

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

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 leading-tight">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <span className="font-mono text-xs text-foreground tabular-nums">
        {value}
      </span>
    </div>
  );
}

function StatColumn({
  children,
  divider,
}: {
  children: React.ReactNode;
  divider?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-0.5 min-w-0 sm:min-w-[100px]",
        divider && "border-l border-border pl-4",
      )}
    >
      {children}
    </div>
  );
}

function HeaderStats({
  state,
  className,
}: {
  state: EnginePayload;
  className?: string;
}) {
  if (!TRACKING_STATES.includes(state.state)) return null;
  const p = state.pointing;
  const ra = p.valid ? formatRa(p.ra_deg) : "--";
  const dec = p.valid ? formatDec(p.dec_deg) : "--";
  const roll = p.valid ? `${p.roll_deg.toFixed(1)}°` : "--";
  const matches = p.valid ? String(p.matches) : "--";
  const prob = p.valid ? p.prob.toExponential(1) : "--";
  const age =
    p.solve_age_s !== null ? `${p.solve_age_s.toFixed(1)}s` : "--";

  return (
    <div className={cn("flex items-stretch gap-4", className)}>
      <StatColumn>
        <Stat label="RA" value={ra} />
        <Stat label="Dec" value={dec} />
      </StatColumn>
      <StatColumn divider>
        <Stat label="Roll" value={roll} />
        <Stat label="Matches" value={matches} />
      </StatColumn>
      <StatColumn divider>
        <Stat label="Prob" value={prob} />
        <Stat label="Age" value={age} />
      </StatColumn>
      <div aria-hidden className="border-l border-border self-stretch" />
    </div>
  );
}

export function StateHeader({ state }: Props) {
  return (
    <>
      {/* Top header: logo + (inline stats at lg+) + audio toggle */}
      <div className="flex items-center justify-between gap-4 pb-2 border-b border-border">
        <img
          src={`${import.meta.env.BASE_URL}inapp-title.png`}
          alt="PushNav"
          className="h-8 w-auto"
        />
        <div className="flex items-center gap-4">
          <HeaderStats state={state} className="hidden lg:flex" />
          <Button
            variant="ghost"
            size="icon"
            onClick={() =>
              api.setSettings({ audio_enabled: !state.audio_enabled })
            }
            title={state.audio_enabled ? "Mute audio" : "Unmute audio"}
          >
            {state.audio_enabled ? (
              <Volume2 className="w-4 h-4" />
            ) : (
              <VolumeX className="w-4 h-4" />
            )}
          </Button>
        </div>
      </div>
      {/* Stats island: shown below the header at < lg */}
      <HeaderStats
        state={state}
        className="lg:hidden justify-end mt-2 pb-2 border-b border-border"
      />
    </>
  );
}
