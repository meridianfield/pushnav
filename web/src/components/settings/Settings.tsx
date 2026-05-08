import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { QRCodeSVG } from "qrcode.react";
import { ActivityDot } from "@/components/ActivityDot";
import { api } from "@/lib/api";
import type { EnginePayload } from "@/lib/types";

interface Props {
  state: EnginePayload;
  showStars: boolean;
  setShowStars: (v: boolean) => void;
}

export function Settings({ state, showStars, setShowStars }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-primary">Settings</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
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
        <div>
          <div className="text-sm font-medium mb-1">Phone web URL</div>
          {state.webserver.url ? (
            <div className="flex items-center gap-3">
              <QRCodeSVG value={state.webserver.url} size={96}
                         bgColor="#0a0000" fgColor="#ff4646" />
              <code className="text-xs break-all">{state.webserver.url}</code>
            </div>
          ) : (
            <div className="text-xs text-muted-foreground">No LAN IP detected</div>
          )}
        </div>
        <Separator />
        <Row label={
          <span>
            Stellarium <ActivityDot active={state.stellarium.active} />
          </span>
        }>
          <code className="text-xs">{state.stellarium.address ?? "off"}</code>
        </Row>
        <Row label={
          <span>
            LX200 (SkySafari) <ActivityDot active={state.lx200.active} />
          </span>
        }>
          <code className="text-xs">{state.lx200.address ?? "off"}</code>
        </Row>
        <Separator />
        <div>
          <div className="text-sm font-medium mb-2 text-primary">Advanced solver</div>
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
                api.setAdvanced({ min_matches: Number(e.currentTarget.value) })
              }
            />
          </Row>
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
                api.setAdvanced({ max_prob: Number(e.currentTarget.value) })
              }
            />
          </Row>
        </div>
      </CardContent>
    </Card>
  );
}

function Row({ label, children }: { label: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm">{label}</span>
      {children}
    </div>
  );
}
