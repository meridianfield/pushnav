import { useEffect, useState } from "react";
import { useEngineState } from "@/hooks/useEngineState";
import { useView } from "@/hooks/useView";
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
import { WhatToSee } from "@/components/catalog/WhatToSee";

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
  const [view, setView] = useView();

  return (
    <>
      <Splash state={state} />
      <ErrorModal state={state} />
      {state && (
        <div className="bg-background text-foreground min-h-screen">
          {/* Header + grid always span at least one viewport height. The grid
              expands (flex-1) to consume any leftover space so any below-the-
              fold content (DebugPanel) always starts past the viewport. */}
          <section
            className={
              view === "catalog"
                ? "min-h-screen lg:h-screen lg:overflow-hidden flex flex-col"
                : "min-h-screen flex flex-col"
            }
          >
            <div className="max-w-5xl mx-auto px-2 pt-2 w-full shrink-0">
              <StateHeader state={state} view={view} onViewChange={setView} />
            </div>
            {view === "navigation" ? (
              <div className="grid md:grid-cols-3 gap-2 max-w-5xl mx-auto px-2 pt-3 pb-2 items-stretch w-full flex-1">
                <div className="md:col-span-2 flex flex-col gap-2">
                  <LiveView state={state} showStars={showStars} />
                  <StepIndicator state={state} />
                  {/* Wizard fills the remaining column height so its bottom
                      aligns with the right column's Settings card. The
                      [&>*]:flex-1 selector targets Wizard's direct DOM child
                      (the Card emitted by whichever step renders) and makes
                      it flex-1 within this growing wrapper. */}
                  <div className="flex-1 flex flex-col [&>*]:flex-1">
                    <Wizard state={state} />
                  </div>
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
            ) : (
              <div className="max-w-5xl mx-auto px-2 pt-3 pb-2 w-full flex-1 min-h-0">
                <WhatToSee
                  state={state}
                  onSwitchToNavigation={() => setView("navigation")}
                />
              </div>
            )}
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
