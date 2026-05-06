import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { EnginePayload } from "@/lib/types";

interface Props { state: EnginePayload | null }

export function Splash({ state }: Props) {
  if (state === null) {
    return (
      <Dialog open>
        <DialogContent>
          <DialogHeader><DialogTitle>Connecting…</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">Waiting for engine.</p>
        </DialogContent>
      </Dialog>
    );
  }
  if (!state.camera.connected) {
    return (
      <Dialog open>
        <DialogContent>
          <DialogHeader><DialogTitle>Camera not found</DialogTitle></DialogHeader>
          <p className="text-sm">Plug in the USB camera and restart PushNav.</p>
        </DialogContent>
      </Dialog>
    );
  }
  return null;
}
