import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";

interface Props {
  /** Applied offset in minutes (committed via Set). */
  appliedOffsetMin: number;
  /** Called with the new committed offset when the user taps Set. */
  onApply: (offsetMin: number) => void;
}

const MAX_MIN = 360;  // 6 hours

function formatOffset(min: number): string {
  if (min === 0) return "Now";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h > 0 ? `+${h}h ${m}m` : `+${m}m`;
}

function appliedTimeLabel(offsetMin: number): string {
  const t = new Date(Date.now() + offsetMin * 60_000);
  const hh = t.getHours().toString().padStart(2, "0");
  const mm = t.getMinutes().toString().padStart(2, "0");
  return `${hh}:${mm}`;
}

export function TimeControl({ appliedOffsetMin, onApply }: Props) {
  // Local preview slider value — not committed until "Set".
  const [preview, setPreview] = useState(appliedOffsetMin);

  useEffect(() => {
    setPreview(appliedOffsetMin);
  }, [appliedOffsetMin]);

  const dirty = preview !== appliedOffsetMin;

  return (
    <div className="flex items-center gap-3 w-full">
      <div className="flex flex-col text-xs leading-tight shrink-0 min-w-[80px]">
        <span className="text-muted-foreground">{formatOffset(appliedOffsetMin)}</span>
        <span className="font-mono text-foreground">
          {appliedTimeLabel(appliedOffsetMin)}
        </span>
      </div>
      <div className="flex-1 min-w-0">
        <Slider
          min={0}
          max={MAX_MIN}
          step={5}
          value={[preview]}
          onValueChange={([v]) => setPreview(v)}
        />
      </div>
      <span className="text-xs text-muted-foreground min-w-[60px] text-right tabular-nums shrink-0">
        {formatOffset(preview)}
      </span>
      <Button
        size="sm"
        disabled={!dirty}
        onClick={() => onApply(preview)}
      >
        Set
      </Button>
      <Button
        size="sm"
        variant="outline"
        disabled={appliedOffsetMin === 0 && preview === 0}
        onClick={() => {
          setPreview(0);
          onApply(0);
        }}
      >
        Reset
      </Button>
    </div>
  );
}
