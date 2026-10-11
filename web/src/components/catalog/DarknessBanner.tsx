import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { darknessAt } from "@/lib/astronomy";

interface Props {
  location: { latitude: number; longitude: number };
  /** Wall-clock time the visibility is computed for. */
  evalAt: Date;
  /** Applied observation-time offset in minutes. */
  appliedOffsetMin: number;
  onApply: (offsetMin: number) => void;
}

function hhmm(t: Date): string {
  return `${t.getHours().toString().padStart(2, "0")}:${t.getMinutes().toString().padStart(2, "0")}`;
}

/** Warns when the chosen time isn't astronomically dark yet, with a jump to when it is. */
export function DarknessBanner({ location, evalAt, appliedOffsetMin, onApply }: Props) {
  const info = useMemo(
    () => darknessAt({ latDeg: location.latitude, lonDeg: location.longitude, date: evalAt }),
    [location, evalAt],
  );
  if (info.status === "dark") return null;

  const target = "darkFrom" in info ? info.darkFrom : info.darkest;
  // Round up to the slider's 5-minute step so the jump lands in darkness
  const jumpMin =
    appliedOffsetMin + Math.ceil((target.getTime() - evalAt.getTime()) / 60_000 / 5) * 5;

  return (
    <div className="flex items-center gap-3 rounded-lg border border-primary/50 bg-primary/10 px-3 py-2 text-xs">
      <div className="flex-1 min-w-0 leading-snug">
        <span className="font-semibold text-foreground">
          {info.status === "day" ? "Daytime" : "Twilight"} at {hhmm(evalAt)}.
        </span>{" "}
        <span className="text-muted-foreground">
          {"darkFrom" in info
            ? `The sky gets dark at ${hhmm(info.darkFrom)}. Until then, most of these objects won't show.`
            : `The sky doesn't get fully dark tonight. It's darkest around ${hhmm(info.darkest)}, with the Sun ${Math.round(-info.darkestSunAltDeg)}° below the horizon.`}
        </span>
      </div>
      <Button size="sm" variant="outline" className="shrink-0" onClick={() => onApply(jumpMin)}>
        Show then
      </Button>
    </div>
  );
}
