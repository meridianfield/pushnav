import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { api } from "@/lib/api";
import type { EnginePayload } from "@/lib/types";

export function SyncStep({ state }: { state: EnginePayload }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Step 2 — Sync</CardTitle>
        <CardDescription>
          Pick any bright star you can see in the sky. It doesn't matter
          which one. You don't need to know its name. Sirius, Vega,
          Betelgeuse, or just "that bright one over there" will do. Center
          that star in your eyepiece as accurately as you can. Use a
          higher-magnification eyepiece for better accuracy. The more
          centered it is, the more accurate your push-to guidance will be
          for the rest of the session.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {state.sync.error && (
          <Alert variant="destructive">
            <AlertDescription>{state.sync.error}</AlertDescription>
          </Alert>
        )}
        <div className="flex flex-wrap gap-2">
          <Button
            disabled={state.sync.in_progress}
            onClick={() => api.wizardAdvance()}
          >
            {state.sync.in_progress ? "Solving…" : "Solve frame"}
          </Button>
          {state.has_calibration && (
            <Button variant="outline" onClick={() => api.useCalibration()}>
              Use previous calibration
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
