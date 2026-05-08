import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { EnginePayload } from "@/lib/types";

const DEFAULT_SHOW_STARS = false;
const DEFAULT_AUDIO_ENABLED = true;
const DEFAULT_MIN_MATCHES = 8;
const DEFAULT_MAX_PROB = 0.2;

interface Props {
  state: EnginePayload;
  showStars: boolean;
  setShowStars: (v: boolean) => void;
  className?: string;
}

export function Settings({ state, showStars, setShowStars, className }: Props) {
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

  const saveLocation = async () => {
    if (!valid) return;
    await api.setSettings({ location: { latitude: lat, longitude: lon } });
  };

  const clearLocation = async () => {
    setLatInput("");
    setLonInput("");
    await api.setSettings({ location: null });
  };

  function resetToDefaults() {
    setShowStars(DEFAULT_SHOW_STARS);
    api
      .setSettings({ audio_enabled: DEFAULT_AUDIO_ENABLED })
      .catch(console.error);
    api
      .setAdvanced({
        min_matches: DEFAULT_MIN_MATCHES,
        max_prob: DEFAULT_MAX_PROB,
      })
      .catch(console.error);
  }

  return (
    <Card className={cn(className)}>
      <CardHeader>
        <CardTitle className="text-primary">Settings</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col flex-1 space-y-2">
        <Row label="Show detected stars">
          <Switch
            checked={showStars}
            onCheckedChange={(v) => setShowStars(v)}
          />
        </Row>
        <Row label="Audio feedback">
          <Switch
            checked={state.audio_enabled}
            onCheckedChange={(v) => api.setSettings({ audio_enabled: v })}
          />
        </Row>
        <Separator />
        <div className="space-y-2">
          <div className="text-sm font-medium text-primary">
            Advanced solver
          </div>
          <Row label="Min matches">
            <Input
              type="number"
              min={3}
              max={50}
              step={1}
              defaultValue={state.min_matches}
              key={`min-${state.min_matches}`}
              className="w-20 h-8"
              onBlur={(e) =>
                api.setAdvanced({
                  min_matches: Number(e.currentTarget.value),
                })
              }
            />
          </Row>
          <p className="text-xs text-muted-foreground leading-snug">
            Stars matched before a solve is accepted. Higher = stricter.
          </p>
          <Row label="Max prob">
            <Input
              type="number"
              min={0}
              max={1}
              step={0.01}
              defaultValue={state.max_prob}
              key={`max-${state.max_prob}`}
              className="w-20 h-8"
              onBlur={(e) =>
                api.setAdvanced({
                  max_prob: Number(e.currentTarget.value),
                })
              }
            />
          </Row>
          <p className="text-xs text-muted-foreground leading-snug">
            Max false-match probability. Lower = stricter.
          </p>
        </div>
        <Separator />
        <div className="space-y-2">
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
              onClick={saveLocation}
              disabled={!dirty || !valid}
            >
              Save
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={clearLocation}
              disabled={!hasManual}
            >
              Clear
            </Button>
          </div>
          <p className="text-xs text-muted-foreground leading-snug">
            Manual fallback used by the catalog when Stellarium isn't connected.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="w-full mt-auto"
          onClick={resetToDefaults}
        >
          Reset to defaults
        </Button>
      </CardContent>
    </Card>
  );
}

function Row({
  label,
  children,
}: {
  label: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm">{label}</span>
      {children}
    </div>
  );
}
