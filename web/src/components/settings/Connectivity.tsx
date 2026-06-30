import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { QRCodeSVG } from "qrcode.react";
import { ActivityDot } from "@/components/ActivityDot";
import { api } from "@/lib/api";
import type { EnginePayload } from "@/lib/types";

interface Props {
  state: EnginePayload;
}

export function Connectivity({ state }: Props) {
  const [showQR, setShowQR] = useState(false);
  const url = state.webserver.url;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-primary">Connectivity</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="space-y-1">
          <div className="text-sm font-medium">Mobile phone URL</div>
          {url ? (
            <>
              <code className="block text-xs break-all">{url}</code>
              <button
                type="button"
                onClick={() => setShowQR((v) => !v)}
                className="text-xs text-primary underline-offset-2 hover:underline"
              >
                {showQR ? "Hide QR code" : "Show QR code"}
              </button>
              {showQR && (
                <div className="pt-1">
                  <QRCodeSVG
                    value={url}
                    size={128}
                    bgColor="#0a0000"
                    fgColor="#ff4646"
                  />
                </div>
              )}
            </>
          ) : (
            <div className="text-xs text-muted-foreground">
              No LAN IP detected
            </div>
          )}
        </div>
        <Separator />
        <Row
          label={
            <span>
              Stellarium (desktop) <ActivityDot active={state.stellarium.active} />
            </span>
          }
        >
          <code className="text-xs">{state.stellarium.address ?? "off"}</code>
        </Row>
        <Row
          label={
            <span>
              LX200 (SkySafari / Stellarium Mobile) <ActivityDot active={state.lx200.active} />
            </span>
          }
        >
          <code className="text-xs">{state.lx200.address ?? "off"}</code>
        </Row>
        <div className="flex items-center justify-between pl-2">
          <span className="text-xs text-muted-foreground">Coordinate epoch</span>
          <div className="flex gap-1">
            {(["jnow", "j2000"] as const).map((e) => (
              <button
                key={e}
                type="button"
                onClick={() => api.setSettings({ lx200_epoch: e })}
                className={
                  (state.lx200.epoch ?? "jnow") === e
                    ? "rounded bg-primary px-2 py-0.5 text-xs text-primary-foreground"
                    : "rounded px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground"
                }
              >
                {e === "jnow" ? "JNow" : "J2000"}
              </button>
            ))}
          </div>
        </div>
        <div className="pl-2 text-[10px] leading-tight text-muted-foreground">
          JNow for SkySafari (standard). Switch to J2000 if Stellarium Mobile PLUS
          centers slightly off target.
        </div>
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
