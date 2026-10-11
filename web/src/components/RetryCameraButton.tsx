import { useState } from "react";
import { RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export function RetryCameraButton() {
  const [retrying, setRetrying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const onClick = async () => {
    setError(null);
    setRetrying(true);
    try {
      const { connected } = await api.retryCamera();
      if (!connected) setError("Still not detected");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRetrying(false);
    }
  };
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={onClick}
      disabled={retrying}
      title={error ?? "Retry camera detection"}
      className="gap-1"
    >
      <RefreshCcw className={cn(retrying && "animate-spin")} />
      {retrying ? "Detecting…" : "Retry camera"}
    </Button>
  );
}
