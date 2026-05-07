import { cn } from "@/lib/utils";
import type { EnginePayload, EngineState } from "@/lib/types";

const STEPS: { num: number; label: string; states: EngineState[] }[] = [
  { num: 1, label: "Camera Setup",          states: ["SETUP"] },
  { num: 2, label: "Sync Scope",            states: ["SYNC", "SYNC_CONFIRM"] },
  { num: 3, label: "Orientation detection", states: ["CALIBRATE"] },
  { num: 4, label: "Tracking",              states: ["WARMING_UP", "TRACKING"] },
];

export function StepIndicator({ state }: { state: EnginePayload }) {
  const currentState = state.state;
  return (
    <div className="grid grid-cols-4 w-full text-sm font-medium select-none">
      {STEPS.map((step, i) => {
        const active = step.states.includes(currentState);
        return (
          <div
            key={step.num}
            className={cn(
              "px-2 py-2 text-center border border-border",
              i > 0 && "border-l-0",
              active
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground",
            )}
          >
            <span className="font-mono mr-1.5">{step.num}</span>
            {step.label}
          </div>
        );
      })}
    </div>
  );
}
