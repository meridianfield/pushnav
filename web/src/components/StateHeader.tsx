import { Volume2, VolumeX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { EnginePayload } from "@/lib/types";

interface Props {
  state: EnginePayload;
}

export function StateHeader({ state }: Props) {
  return (
    <div className="flex items-center justify-between gap-3 pb-3 border-b border-border">
      <span className="font-semibold text-lg tracking-tight text-primary">
        PushNav
      </span>
      <Button
        variant="ghost"
        size="icon"
        onClick={() =>
          api.setSettings({ audio_enabled: !state.audio_enabled })
        }
        title={state.audio_enabled ? "Mute audio" : "Unmute audio"}
      >
        {state.audio_enabled ? (
          <Volume2 className="w-4 h-4" />
        ) : (
          <VolumeX className="w-4 h-4" />
        )}
      </Button>
    </div>
  );
}
