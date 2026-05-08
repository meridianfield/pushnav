import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { altAzFromRaDec, parseDec, parseRA } from "@/lib/astronomy";
import { azimuthCompass, type CatalogObject } from "@/lib/catalogTypes";
import type { CatalogFilterState } from "@/components/catalog/CatalogFilters";

const ALT_THRESHOLD_DEG = 20;

type SortKey = "name" | "type" | "mag" | "alt";
type SortDir = "asc" | "desc";

interface Props {
  objects: CatalogObject[];
  filters: CatalogFilterState;
  /** Active observer location, or null when not yet set. */
  location: { latitude: number; longitude: number } | null;
  /** Wall-clock time the visibility is computed for. */
  evalAt: Date;
  /** Selected object id (drives detail panel). */
  selectedId: string | null;
  onSelect: (id: string) => void;
}

interface RowData {
  obj: CatalogObject;
  altDeg: number;
  azDeg: number;
}

export function CatalogTable({
  objects, filters, location, evalAt, selectedId, onSelect,
}: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("type");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const rows = useMemo<RowData[]>(() => {
    if (!location) return [];
    const out: RowData[] = [];
    for (const obj of objects) {
      if (!filters.equipment.has(obj.minEquipment)) continue;
      if (!filters.lp.has(obj.lpTolerance)) continue;
      if (!filters.reward.has(obj.visualReward)) continue;
      const raHours = parseRA(obj.rightAscension);
      const decDeg = parseDec(obj.declination);
      if (raHours === null || decDeg === null) continue;
      const { altDeg, azDeg } = altAzFromRaDec({
        raHours, decDeg,
        latDeg: location.latitude, lonDeg: location.longitude,
        date: evalAt,
      });
      if (altDeg < ALT_THRESHOLD_DEG) continue;
      out.push({ obj, altDeg, azDeg });
    }
    return out;
  }, [objects, filters, location, evalAt]);

  const sorted = useMemo(() => {
    const arr = [...rows];
    arr.sort((a, b) => {
      let c = 0;
      switch (sortKey) {
        case "name":
          c = a.obj.name.localeCompare(b.obj.name); break;
        case "type":
          c = (a.obj.subtype ?? a.obj.type).localeCompare(b.obj.subtype ?? b.obj.type);
          break;
        case "mag": {
          const ma = a.obj.magnitude ?? Number.POSITIVE_INFINITY;
          const mb = b.obj.magnitude ?? Number.POSITIVE_INFINITY;
          c = ma - mb; break;
        }
        case "alt":
          c = a.altDeg - b.altDeg; break;
      }
      return sortDir === "asc" ? c : -c;
    });
    return arr;
  }, [rows, sortKey, sortDir]);

  function clickHeader(key: SortKey) {
    if (sortKey === key) setSortDir(sortDir === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir(key === "alt" ? "desc" : "asc"); }
  }

  if (!location) {
    return null;  // empty-state handled by parent
  }
  if (sorted.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
        No objects above {ALT_THRESHOLD_DEG}° altitude with these filters at this time.
        Widen the filters or scrub forward.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-muted/40 text-left text-xs text-muted-foreground uppercase">
          <tr>
            <Th onClick={() => clickHeader("name")} active={sortKey === "name"} dir={sortDir}>
              Name
            </Th>
            <Th onClick={() => clickHeader("type")} active={sortKey === "type"} dir={sortDir}>
              Type
            </Th>
            <Th onClick={() => clickHeader("mag")} active={sortKey === "mag"} dir={sortDir}>
              Mag
            </Th>
            <Th onClick={() => clickHeader("alt")} active={sortKey === "alt"} dir={sortDir}>
              Alt
            </Th>
            <th className="px-2 py-1.5">Az</th>
            <th className="px-2 py-1.5">Reward</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(({ obj, altDeg, azDeg }) => (
            <tr
              key={obj.id}
              onClick={() => onSelect(obj.id)}
              className={cn(
                "cursor-pointer hover:bg-muted/30 border-t border-border",
                selectedId === obj.id && "bg-primary/15"
              )}
            >
              <td className="px-2 py-1.5">
                <span className="font-mono">{obj.designation}</span>{" "}
                <span className="text-muted-foreground">{obj.name}</span>
              </td>
              <td className="px-2 py-1.5 text-muted-foreground">
                {obj.subtype ?? obj.type}
              </td>
              <td className="px-2 py-1.5 tabular-nums">
                {typeof obj.magnitude === "number" ? obj.magnitude.toFixed(1) : "—"}
              </td>
              <td className="px-2 py-1.5 tabular-nums">{Math.round(altDeg)}°</td>
              <td className="px-2 py-1.5 font-mono">{azimuthCompass(azDeg)}</td>
              <td className="px-2 py-1.5">
                <RewardChip reward={obj.visualReward} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Th({
  children, onClick, active, dir,
}: { children: React.ReactNode; onClick: () => void; active: boolean; dir: SortDir }) {
  return (
    <th
      className={cn("px-2 py-1.5 cursor-pointer select-none", active && "text-foreground")}
      onClick={onClick}
    >
      {children} {active && (dir === "asc" ? "▲" : "▼")}
    </th>
  );
}

function RewardChip({ reward }: { reward: "high" | "moderate" | "low" }) {
  const { letter, cls } = {
    high:     { letter: "H", cls: "bg-primary/30 text-foreground" },
    moderate: { letter: "M", cls: "bg-muted/60 text-foreground" },
    low:      { letter: "L", cls: "bg-muted/30 text-muted-foreground" },
  }[reward];
  return (
    <span className={cn("inline-flex items-center justify-center w-5 h-5 rounded-sm text-[10px] font-semibold", cls)}>
      {letter}
    </span>
  );
}
