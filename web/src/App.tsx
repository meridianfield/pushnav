import { useEngineState } from "@/hooks/useEngineState";
import { LiveView } from "@/components/live-view/LiveView";
import { CameraControls } from "@/components/controls/CameraControls";
import { Wizard } from "@/components/wizard/Wizard";
import { Settings } from "@/components/settings/Settings";
import { Splash } from "@/components/splash/Splash";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function App() {
  const state = useEngineState();
  return (
    <>
      <Splash state={state} />
      {state && (
        <div className="min-h-screen bg-background text-foreground p-4">
          <div className="grid md:grid-cols-3 gap-4 max-w-7xl mx-auto">
            <div className="md:col-span-2 space-y-4">
              <LiveView state={state} />
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
                  <Settings state={state} />
                </TabsContent>
              </Tabs>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
