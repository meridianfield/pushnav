import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import objectsData from "@/data/objects.json";
import type { CatalogObject } from "@/lib/catalogTypes";
import type { EnginePayload } from "@/lib/types";
import {
  CatalogFilters,
  SelectedFiltersLine,
  useCatalogFilters,
} from "./CatalogFilters";
import { CatalogTable } from "./CatalogTable";
import { CatalogDetail } from "./CatalogDetail";
import { TimeControl } from "./TimeControl";

const objects = objectsData as CatalogObject[];

interface Props {
  state: EnginePayload;
  onSwitchToNavigation: () => void;
}

export function WhatToSee({ state, onSwitchToNavigation }: Props) {
  const [filters, setFilters] = useCatalogFilters();
  const [appliedOffsetMin, setAppliedOffsetMin] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);

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

  if (!location) {
    return (
      <Card className="p-6 text-sm">
        <h3 className="font-semibold mb-2">Set your observing location</h3>
        <p className="text-muted-foreground mb-3">
          The catalog computes which objects are above the horizon for you. We
          need your latitude and longitude to do that.
        </p>
        <p className="text-muted-foreground">
          Open <span className="text-foreground">Settings → Location</span> to
          enter your coordinates manually, or connect Stellarium and we'll pick
          up its location automatically.
        </p>
      </Card>
    );
  }

  return (
    <div className="flex flex-col lg:grid lg:grid-cols-3 lg:grid-rows-1 gap-3 h-full lg:min-h-0">
      {/* Left island: filters + selected chips + time + scrollable table */}
      <Card className="lg:col-span-2 flex flex-col gap-2 px-3 py-3 lg:min-h-0">
        <CatalogFilters value={filters} onChange={setFilters} />
        <SelectedFiltersLine value={filters} />

        <div className="border-t border-border/60 -mx-3" />

        <div className="flex flex-col gap-1">
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Observation Time
          </div>
          <TimeControl
            appliedOffsetMin={appliedOffsetMin}
            onApply={setAppliedOffsetMin}
          />
        </div>

        <div className="border-t border-border/60 -mx-3" />

        <div className="lg:flex-1 lg:min-h-0 lg:overflow-y-auto pushnav-scrollbar -mx-3 px-3">
          <CatalogTable
            objects={objects}
            filters={filters}
            location={location}
            evalAt={evalAt}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        </div>
      </Card>

      {/* Right island: detail panel — Card is the grid item directly so it
          stretches to the full row height, matching the left island. */}
      <CatalogDetail
        object={selected}
        location={location}
        evalAt={evalAt}
        onTargetSet={onSwitchToNavigation}
        className="lg:col-span-1 lg:min-h-0 lg:overflow-y-auto pushnav-scrollbar"
      />
    </div>
  );
}
