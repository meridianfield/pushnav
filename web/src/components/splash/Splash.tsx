import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { EnginePayload } from "@/lib/types";

interface Props { state: EnginePayload | null }

export function Splash({ state }: Props) {
  if (state === null) {
    return (
      <Dialog open>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Connecting…</DialogTitle>
            <DialogDescription>Waiting for engine.</DialogDescription>
          </DialogHeader>
        </DialogContent>
      </Dialog>
    );
  }
  if (!state.camera.connected) {
    return (
      <Dialog open>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Camera not found</DialogTitle>
            <DialogDescription>
              Plug in the USB camera and restart PushNav.
            </DialogDescription>
          </DialogHeader>
        </DialogContent>
      </Dialog>
    );
  }
  return null;
}
