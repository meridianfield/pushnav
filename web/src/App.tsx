import { useEffect, useState } from "react";
import { useEngineState } from "@/hooks/useEngineState";
import { LiveView } from "@/components/live-view/LiveView";
import { CameraControls } from "@/components/controls/CameraControls";
import { Wizard } from "@/components/wizard/Wizard";
import { Settings } from "@/components/settings/Settings";
import { Splash } from "@/components/splash/Splash";
import { ErrorModal } from "@/components/ErrorModal";
import { StateHeader } from "@/components/StateHeader";
import { GotoTargetBanner } from "@/components/GotoTargetBanner";
import { PlateSolveStats } from "@/components/PlateSolveStats";
import { DebugPanel } from "@/components/debug/DebugPanel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

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
  const [showStars, setShowStars] = useLocalStorageBool("pushnav.show_stars", true);

  return (
    <>
      <Splash state={state} />
      <ErrorModal state={state} />
      {state && (
        <div className="min-h-screen bg-background text-foreground">
          <div className="max-w-7xl mx-auto px-4 pt-4">
            <StateHeader state={state} />
            <GotoTargetBanner state={state} />
          </div>
          <div className="grid md:grid-cols-3 gap-4 max-w-7xl mx-auto p-4">
            <div className="md:col-span-2 space-y-4">
              <LiveView state={state} showStars={showStars} />
              <Wizard state={state} />
            </div>
            <div className="space-y-4">
              <Tabs defaultValue="camera">
                <TabsList>
                  <TabsTrigger value="camera">Camera</TabsTrigger>
                  <TabsTrigger value="settings">Settings</TabsTrigger>
                </TabsList>
                <TabsContent value="camera">
                  <CameraControls controls={state.controls} />
                </TabsContent>
                <TabsContent value="settings">
                  <Settings
                    state={state}
                    showStars={showStars}
                    setShowStars={setShowStars}
                  />
                </TabsContent>
              </Tabs>
              <PlateSolveStats state={state} />
              {state.dev_mode && <DebugPanel state={state} />}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
