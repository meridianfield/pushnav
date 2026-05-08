import { useEffect, useState } from "react";
import { useEngineState } from "@/hooks/useEngineState";
import { LiveView } from "@/components/live-view/LiveView";
import { CameraControls } from "@/components/controls/CameraControls";
import { Wizard } from "@/components/wizard/Wizard";
import { Settings } from "@/components/settings/Settings";
import { Connectivity } from "@/components/settings/Connectivity";
import { Splash } from "@/components/splash/Splash";
import { ErrorModal } from "@/components/ErrorModal";
import { StateHeader } from "@/components/StateHeader";
import { StepIndicator } from "@/components/StepIndicator";
import { DebugPanel } from "@/components/debug/DebugPanel";

function useLocalStorageBool(key: string, defaultValue: boolean) {
  const [v, setV] = useState<boolean>(() => {
    const saved = localStorage.getItem(key);
    return saved === null ? defaultValue : saved === "true";
  });
  useEffect(() => {
    localStorage.setItem(key, String(v));
  }, [key, v]);
  return [v, setV] as const;
}

export default function App() {
  const state = useEngineState();
  const [showStars, setShowStars] = useLocalStorageBool("pushnav.show_stars", false);

  return (
    <>
      <Splash state={state} />
      <ErrorModal state={state} />
      {state && (
        <div className="bg-background text-foreground min-h-screen">
          {/* Header + grid always span at least one viewport height. The grid
              expands (flex-1) to consume any leftover space so any below-the-
              fold content (DebugPanel) always starts past the viewport. */}
          <section className="min-h-screen flex flex-col">
            <div className="max-w-5xl mx-auto px-2 pt-2 w-full shrink-0">
              <StateHeader state={state} />
            </div>
            <div className="grid md:grid-cols-3 gap-2 max-w-5xl mx-auto px-2 pt-3 pb-2 items-stretch w-full flex-1">
              <div className="md:col-span-2 flex flex-col gap-2">
                <LiveView state={state} showStars={showStars} />
                <StepIndicator state={state} />
                <Wizard state={state} />
              </div>
              <div className="flex flex-col gap-2">
                <CameraControls controls={state.controls} />
                <Connectivity state={state} />
                <Settings
                  state={state}
                  showStars={showStars}
                  setShowStars={setShowStars}
                  className="flex-1"
                />
              </div>
            </div>
          </section>
          {state.dev_mode && (
            <section className="max-w-5xl mx-auto px-2 pb-2 w-full">
              <DebugPanel state={state} />
            </section>
          )}
        </div>
      )}
    </>
  );
}
