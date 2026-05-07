import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { EnginePayload } from "@/lib/types";

export function SyncConfirmStep({ state }: { state: EnginePayload }) {
  const candidates = state.sync.candidates;
  const selectedIdx = state.sync.selected_idx;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Step 2b — Confirm sync star</CardTitle>
        <CardDescription>
          Tap the star you actually centered. The brightest auto-selected pick is highlighted.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="flex flex-wrap gap-2">
          {candidates.map((c) => (
            <Button
              key={c.idx}
              variant={c.idx === selectedIdx ? "default" : "outline"}
              size="sm"
              onClick={() => api.syncSelect(c.idx)}
              className="h-auto py-2 flex flex-col items-start gap-1"
            >
              <span className="font-medium">{c.name}</span>
              <Badge variant="secondary">mag {c.magnitude.toFixed(1)}</Badge>
            </Button>
          ))}
        </div>
        <div className="flex gap-2">
          <Button onClick={() => api.wizardAdvance()}>Confirm</Button>
          <Button variant="outline" onClick={() => api.syncRetry()}>Re-solve</Button>
        </div>
      </CardContent>
    </Card>
  );
}
