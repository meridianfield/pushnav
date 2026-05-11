import { Card } from "@/components/ui/card";
import type { CatalogObject } from "@/lib/catalogTypes";
import {
  CatalogFilters, SelectedFiltersLine, useCatalogFilters,
} from "../CatalogFilters";
import { CatalogTable } from "../CatalogTable";
import { TimeControl } from "../TimeControl";

interface Props {
  objects: CatalogObject[];
  location: { latitude: number; longitude: number } | null;
  evalAt: Date;
  appliedOffsetMin: number;
  setAppliedOffsetMin: (m: number) => void;
  selectedId: string | null;
  setSelectedId: (id: string | null) => void;
}

export function BuddyTab({
  objects, location, evalAt,
  appliedOffsetMin, setAppliedOffsetMin,
  selectedId, setSelectedId,
}: Props) {
  const [filters, setFilters] = useCatalogFilters();

  return (
    <Card className="lg:col-span-2 flex flex-col gap-2 px-3 py-3 min-h-0 max-h-[70vh] lg:max-h-none">
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

      <div className="flex-1 min-h-0 overflow-y-auto pushnav-scrollbar -mx-3 px-3">
        {location ? (
          <CatalogTable
            objects={objects}
            filters={filters}
            location={location}
            evalAt={evalAt}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        ) : (
          <div className="text-sm text-muted-foreground p-2">
            Set your observing location on the right to see visible objects.
          </div>
        )}
      </div>
    </Card>
  );
}
