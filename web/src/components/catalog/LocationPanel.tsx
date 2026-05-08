import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import type { EnginePayload } from "@/lib/types";

interface Props {
  state: EnginePayload;
}

export function LocationPanel({ state }: Props) {
  const manualLat =
    state.location?.source === "manual" ? state.location.latitude : null;
  const manualLon =
    state.location?.source === "manual" ? state.location.longitude : null;
  const [latInput, setLatInput] = useState(
    manualLat !== null ? String(manualLat) : "",
  );
  const [lonInput, setLonInput] = useState(
    manualLon !== null ? String(manualLon) : "",
  );

  useEffect(() => {
    if (state.location?.source === "manual") {
      setLatInput(String(state.location.latitude));
      setLonInput(String(state.location.longitude));
    }
  }, [
    state.location?.source,
    state.location?.latitude,
    state.location?.longitude,
  ]);

  const lat = parseFloat(latInput);
  const lon = parseFloat(lonInput);
  const valid =
    Number.isFinite(lat) &&
    Number.isFinite(lon) &&
    lat >= -90 &&
    lat <= 90 &&
    lon >= -180 &&
    lon <= 180;
  const dirty =
    String(manualLat ?? "") !== latInput ||
    String(manualLon ?? "") !== lonInput;
  const hasManual = manualLat !== null && manualLon !== null;

  const save = async () => {
    if (!valid) return;
    await api.setSettings({ location: { latitude: lat, longitude: lon } });
  };

  const clear = async () => {
    setLatInput("");
    setLonInput("");
    await api.setSettings({ location: null });
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <Label className="text-sm font-medium text-primary">Location</Label>
        <span className="text-xs text-muted-foreground font-mono">
          {state.location?.source ?? "—"}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Input
          type="number"
          step="0.0001"
          placeholder="Lat"
          value={latInput}
          onChange={(e) => setLatInput(e.target.value)}
          className="h-7 text-xs"
        />
        <Input
          type="number"
          step="0.0001"
          placeholder="Lon"
          value={lonInput}
          onChange={(e) => setLonInput(e.target.value)}
          className="h-7 text-xs"
        />
      </div>
      <div className="flex gap-2">
        <Button
          size="sm"
          variant="default"
          onClick={save}
          disabled={!dirty || !valid}
        >
          Save
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={clear}
          disabled={!hasManual}
        >
          Clear
        </Button>
      </div>
      <div className="text-xs text-muted-foreground leading-snug space-y-0.5">
        <div>Latitude: + = North, − = South</div>
        <div>Longitude: + = East, − = West</div>
        <div className="pt-1">
          e.g. New York <span className="font-mono">40.71, −74.01</span> ·
          Sydney <span className="font-mono">−33.87, 151.21</span>
        </div>
      </div>
    </div>
  );
}
