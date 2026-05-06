import { useEngineState } from "@/hooks/useEngineState";

export default function App() {
  const state = useEngineState();
  return (
    <div className="min-h-screen bg-background text-foreground p-8 font-mono">
      <h1 className="text-2xl mb-4">PushNav state</h1>
      <pre className="text-xs">{JSON.stringify(state, null, 2)}</pre>
    </div>
  );
}
