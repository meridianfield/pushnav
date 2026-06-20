import { useState, useEffect } from "react";
import { Slider } from "@/components/ui/slider";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { ControlDescriptor } from "@/lib/types";

interface Props {
  controls: ControlDescriptor[];
}

export function CameraControls({ controls }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Camera</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {controls.map((c) => (
          <ControlRow key={c.id ?? c.name} control={c} />
        ))}
      </CardContent>
    </Card>
  );
}

// Convert a raw control value to a human-readable label using its per-OS unit.
// Exposure controls report platform-specific raw units (issue #26); the slider
// keeps operating on raw min/max/step, only the displayed label is converted.
//   "100us"  (Linux/macOS UVC): milliseconds = value * 0.1
//   "log2s"  (Windows DirectShow): milliseconds = 2^value * 1000
// Anything else (e.g. gain's "raw", or no unit) shows the raw value unchanged.
function formatControlValue(value: number, unit?: string): string {
  let ms: number | null = null;
  if (unit === "100us") ms = value * 0.1;
  else if (unit === "log2s") ms = Math.pow(2, value) * 1000;
  if (ms === null) return String(value);
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)} s`;
  if (ms >= 100) return `${ms.toFixed(0)} ms`;
  return `${ms.toFixed(1)} ms`;
}

function ControlRow({ control }: { control: ControlDescriptor }) {
  const id = control.id ?? control.name ?? "";
  const serverValue = control.cur ?? control.value ?? control.min;
  const [local, setLocal] = useState(serverValue);

  // Reflect server-side updates
  useEffect(() => { setLocal(serverValue); }, [serverValue]);

  const commit = (v: number) => {
    setLocal(v);
    api.setControl(id, v).catch((e) => console.error(e));
  };

  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span>{control.label}</span>
        <span className="text-muted-foreground">{formatControlValue(local, control.unit)}</span>
      </div>
      <Slider
        min={control.min}
        max={control.max}
        step={control.step ?? 1}
        value={[local]}
        onValueChange={([v]) => setLocal(v)}
        onValueCommit={([v]) => commit(v)}
      />
    </div>
  );
}
