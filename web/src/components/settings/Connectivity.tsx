import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { QRCodeSVG } from "qrcode.react";
import { ActivityDot } from "@/components/ActivityDot";
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
              Stellarium <ActivityDot active={state.stellarium.active} />
            </span>
          }
        >
          <code className="text-xs">{state.stellarium.address ?? "off"}</code>
        </Row>
        <Row
          label={
            <span>
              LX200 (SkySafari) <ActivityDot active={state.lx200.active} />
            </span>
          }
        >
          <code className="text-xs">{state.lx200.address ?? "off"}</code>
        </Row>
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
