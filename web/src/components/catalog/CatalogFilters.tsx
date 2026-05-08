import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { Equipment, LpTolerance, VisualReward } from "@/lib/catalogTypes";

const EQUIPMENT: { value: Equipment; label: string }[] = [
  { value: "naked-eye", label: "Naked eye" },
  { value: "binoculars", label: "Binoculars" },
  { value: "small-telescope", label: "Small scope" },
  { value: "medium-telescope", label: "Medium scope" },
  { value: "large-telescope", label: "Large scope" },
];

const LP: { value: LpTolerance; label: string }[] = [
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

const REWARD: { value: VisualReward; label: string }[] = [
  { value: "high", label: "High" },
  { value: "moderate", label: "Moderate" },
  { value: "low", label: "Low" },
];

export interface CatalogFilterState {
  equipment: Set<Equipment>;
  lp: Set<LpTolerance>;
  reward: Set<VisualReward>;
}

interface Props {
  value: CatalogFilterState;
  onChange: (next: CatalogFilterState) => void;
}

export function SelectedFiltersLine({ value }: { value: CatalogFilterState }) {
  const segs: string[] = [];
  if (value.equipment.size < EQUIPMENT.length) {
    segs.push(
      "Equipment: " +
        EQUIPMENT.filter((e) => value.equipment.has(e.value))
          .map((e) => e.label)
          .join(", "),
    );
  }
  if (value.lp.size < LP.length) {
    segs.push(
      "LP: " +
        LP.filter((l) => value.lp.has(l.value))
          .map((l) => l.label)
          .join(", "),
    );
  }
  if (value.reward.size < REWARD.length) {
    segs.push(
      "Reward: " +
        REWARD.filter((r) => value.reward.has(r.value))
          .map((r) => r.label)
          .join(", "),
    );
  }
  if (segs.length === 0) return null;
  return (
    <div className="text-xs text-muted-foreground">{segs.join("  ·  ")}</div>
  );
}

export function CatalogFilters({ value, onChange }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <FilterDropdown
        label="Equipment"
        options={EQUIPMENT}
        selected={value.equipment as Set<string>}
        onChange={(next) => onChange({ ...value, equipment: next as Set<Equipment> })}
      />
      <FilterDropdown
        label="LP tolerance"
        options={LP}
        selected={value.lp as Set<string>}
        onChange={(next) => onChange({ ...value, lp: next as Set<LpTolerance> })}
      />
      <FilterDropdown
        label="Visual reward"
        options={REWARD}
        selected={value.reward as Set<string>}
        onChange={(next) => onChange({ ...value, reward: next as Set<VisualReward> })}
      />
    </div>
  );
}

function FilterDropdown<T extends string>({
  label, options, selected, onChange,
}: {
  label: string;
  options: { value: T; label: string }[];
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
}) {
  const total = options.length;
  const count = selected.size;
  const summary = count === total ? "All" : `${count} of ${total}`;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm">
          {label}: {summary}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56 p-2 space-y-1">
        {options.map((o) => (
          <label key={o.value} className="flex items-center gap-2 cursor-pointer text-sm py-1">
            <Checkbox
              checked={selected.has(o.value)}
              onCheckedChange={(checked) => {
                const next = new Set(selected);
                if (checked) next.add(o.value);
                else next.delete(o.value);
                onChange(next);
              }}
            />
            {o.label}
          </label>
        ))}
      </PopoverContent>
    </Popover>
  );
}

export function useCatalogFilters(): [
  CatalogFilterState,
  (next: CatalogFilterState) => void,
] {
  const [state, setStateRaw] = useState<CatalogFilterState>(() => {
    const eq = JSON.parse(localStorage.getItem("pushnav.catalog.equipment") || "null");
    const lp = JSON.parse(localStorage.getItem("pushnav.catalog.lp") || "null");
    const rw = JSON.parse(localStorage.getItem("pushnav.catalog.reward") || "null");
    return {
      equipment: new Set(eq ?? EQUIPMENT.map((e) => e.value)) as Set<Equipment>,
      lp: new Set(lp ?? LP.map((l) => l.value)) as Set<LpTolerance>,
      reward: new Set(rw ?? REWARD.map((r) => r.value)) as Set<VisualReward>,
    };
  });
  useEffect(() => {
    localStorage.setItem(
      "pushnav.catalog.equipment",
      JSON.stringify([...state.equipment]),
    );
    localStorage.setItem("pushnav.catalog.lp", JSON.stringify([...state.lp]));
    localStorage.setItem("pushnav.catalog.reward", JSON.stringify([...state.reward]));
  }, [state]);
  return [state, setStateRaw];
}
