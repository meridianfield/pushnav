import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
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
            Minimum stars matched before a plate-solve is accepted. Higher
            is stricter (fewer false locks); lower is more permissive (may
            accept noise).
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
            Maximum solve probability of being a false match. Lower is
            stricter (more confident solves only); higher accepts less
            certain solves.
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
