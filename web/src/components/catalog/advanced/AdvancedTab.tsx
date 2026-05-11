import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import { advancedSearch } from "@/lib/advancedSearch";
import type {
  AdvancedEntry, NgcEntry, StarEntry,
} from "@/lib/catalogTypes";
import ngcData from "@/data/openngc.json";
import starData from "@/data/hyg-bright.json";
import { SearchInput } from "./SearchInput";
import { ResultsList } from "./ResultsList";

const ngcList: NgcEntry[] = (ngcData as Omit<NgcEntry, "source">[])
  .map((e) => ({ ...e, source: "ngc" as const }));
const starList: StarEntry[] = (starData as Omit<StarEntry, "source">[])
  .map((e) => ({ ...e, source: "star" as const }));
const allEntries: (NgcEntry | StarEntry)[] = [...ngcList, ...starList];

interface Props {
  selected: AdvancedEntry | null;
  onSelect: (entry: AdvancedEntry | null) => void;
}

export function AdvancedTab({ selected, onSelect }: Props) {
  const [query, setQueryRaw] = useState("");
  const [debounced, setDebounced] = useState("");
  useEffect(() => {
    const id = setTimeout(() => setDebounced(query), 100);
    return () => clearTimeout(id);
  }, [query]);

  const results = useMemo(
    () => advancedSearch(debounced, allEntries) as (NgcEntry | StarEntry)[],
    [debounced],
  );

  const selectedId =
    selected && (selected.source === "ngc" || selected.source === "star")
      ? selected.id
      : null;

  function onPick(id: string, source: "ngc" | "star") {
    const found = allEntries.find((e) => e.source === source && e.id === id);
    onSelect(found ?? null);
  }

  return (
    <Card className="lg:col-span-2 flex flex-col gap-2 px-3 py-3 min-h-0 max-h-[70vh] lg:max-h-none">
      <SearchInput value={query} onChange={setQueryRaw} />
      <div className="border-t border-border/60 -mx-3" />
      <div className="flex-1 min-h-0 overflow-y-auto pushnav-scrollbar -mx-3 px-3">
        {debounced.trim() === "" ? (
          <div className="text-sm text-muted-foreground p-2">
            Type to search ~{ngcList.length + starList.length} objects.
          </div>
        ) : (
          <ResultsList entries={results} selectedId={selectedId} onSelect={onPick} />
        )}
      </div>
      <div className="text-[10px] text-muted-foreground mt-1 px-1 leading-tight">
        Star data:{" "}
        <a href="https://www.astronexus.com/hyg" target="_blank"
           rel="noopener noreferrer" className="underline">HYG database</a>.
        Deep-sky data:{" "}
        <a href="https://github.com/mattiaverga/OpenNGC" target="_blank"
           rel="noopener noreferrer" className="underline">OpenNGC</a>. CC-BY-SA.
      </div>
    </Card>
  );
}
