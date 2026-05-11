import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import objectsData from "@/data/objects.json";
import type { CatalogObject } from "@/lib/catalogTypes";
import type { EnginePayload } from "@/lib/types";
import { CatalogDetail } from "./CatalogDetail";
import { LocationPanel } from "./LocationPanel";
import { BuddyTab } from "./buddy/BuddyTab";

const objects = objectsData as CatalogObject[];
const SELECTED_KEY = "pushnav.catalog.selected";

interface Props {
  state: EnginePayload;
  onSwitchToNavigation: () => void;
}

export function WhatToSee({ state, onSwitchToNavigation }: Props) {
  const [appliedOffsetMin, setAppliedOffsetMin] = useState(0);
  const [selectedId, setSelectedIdState] = useState<string | null>(() => {
    const raw = localStorage.getItem(SELECTED_KEY);
    return raw && objects.some((o) => o.id === raw) ? raw : null;
  });
  const setSelectedId = (id: string | null) => {
    setSelectedIdState(id);
    if (id === null) localStorage.removeItem(SELECTED_KEY);
    else localStorage.setItem(SELECTED_KEY, id);
  };

  const [tickNow, setTickNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setTickNow(Date.now()), 60_000);
    return () => clearInterval(id);
  }, []);

  const evalAt = useMemo(
    () => new Date(tickNow + appliedOffsetMin * 60_000),
    [tickNow, appliedOffsetMin],
  );

  const location = useMemo(() => {
    const loc = state.location;
    if (!loc || loc.latitude === null || loc.longitude === null) return null;
    return { latitude: loc.latitude, longitude: loc.longitude };
  }, [state.location]);

  const selected = useMemo(
    () => objects.find((o) => o.id === selectedId) ?? null,
    [selectedId],
  );

  return (
    <div className="flex flex-col lg:grid lg:grid-cols-3 lg:grid-rows-1 gap-3 lg:h-full lg:min-h-0 lg:overflow-hidden">
      <BuddyTab
        objects={objects}
        location={location}
        evalAt={evalAt}
        appliedOffsetMin={appliedOffsetMin}
        setAppliedOffsetMin={setAppliedOffsetMin}
        selectedId={selectedId}
        setSelectedId={setSelectedId}
      />

      <Card className="lg:col-span-1 lg:min-h-0 lg:overflow-y-auto pushnav-scrollbar flex flex-col gap-3 px-4 py-3 text-sm">
        <LocationPanel state={state} />
        <div className="border-t border-border/60 -mx-4" />
        <CatalogDetail
          input={selected ? { kind: "buddy", object: selected } : null}
          location={location}
          evalAt={evalAt}
          onTargetSet={onSwitchToNavigation}
        />
      </Card>
    </div>
  );
}
