import { cn } from "@/lib/utils";
import type { NgcEntry, StarEntry } from "@/lib/catalogTypes";

type SearchableEntry = NgcEntry | StarEntry;

interface Props {
  entries: SearchableEntry[];
  selectedId: string | null;
  onSelect: (id: string, source: "ngc" | "star") => void;
}

export function ResultsList({ entries, selectedId, onSelect }: Props) {
  if (entries.length === 0) {
    return (
      <div className="text-sm text-muted-foreground p-2">No matches.</div>
    );
  }
  return (
    <ul className="flex flex-col">
      {entries.map((e) => (
        <li key={`${e.source}:${e.id}`}>
          <button
            type="button"
            onClick={() => onSelect(e.id, e.source)}
            className={cn(
              "w-full text-left px-2 py-1 text-xs hover:bg-muted/50",
              selectedId === e.id && "bg-muted text-foreground",
            )}
          >
            <span className="mr-2 inline-block min-w-[2.5rem] text-[10px] uppercase tracking-wider text-muted-foreground">
              {e.source === "ngc" ? "DSO" : "Star"}
            </span>
            <span className="font-mono">{e.id}</span>
            {e.mag !== null && (
              <span className="ml-2 text-muted-foreground">mag {e.mag.toFixed(2)}</span>
            )}
            {e.constellation && (
              <span className="ml-2 text-muted-foreground">{e.constellation}</span>
            )}
          </button>
        </li>
      ))}
    </ul>
  );
}
