import { useState } from "react";
import { ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { altAzFromRaDec, parseDec, parseRA, riseSetTransitUtc } from "@/lib/astronomy";
import { azimuthCompass, type CatalogObject } from "@/lib/catalogTypes";

interface Props {
  object: CatalogObject | null;
  location: { latitude: number; longitude: number } | null;
  evalAt: Date;
  onTargetSet?: () => void;
}

function formatTimeLocal(t: Date | null): string {
  if (!t) return "—";
  const hh = t.getHours().toString().padStart(2, "0");
  const mm = t.getMinutes().toString().padStart(2, "0");
  return `${hh}:${mm}`;
}

function buddyUrl(id: string): string {
  return `https://stargazingbuddy.com/objects/${id}`;
}

export function CatalogDetail({ object, location, evalAt, onTargetSet }: Props) {
  const [setting, setSetting] = useState(false);
  const [setOk, setSetOk] = useState<null | "ok" | "error">(null);

  if (!object) {
    return (
      <Card className="px-4 py-3 text-sm text-muted-foreground">
        Select an object on the left to see details.
      </Card>
    );
  }

  const raHours = parseRA(object.rightAscension);
  const decDeg = parseDec(object.declination);
  let altDeg: number | null = null;
  let azDeg: number | null = null;
  let rise: Date | null = null;
  let set: Date | null = null;
  let transit: Date | null = null;

  if (raHours !== null && decDeg !== null && location) {
    const aa = altAzFromRaDec({
      raHours, decDeg,
      latDeg: location.latitude, lonDeg: location.longitude,
      date: evalAt,
    });
    altDeg = aa.altDeg;
    azDeg = aa.azDeg;
    const rst = riseSetTransitUtc({
      raHours, decDeg,
      latDeg: location.latitude, lonDeg: location.longitude,
      dateUtc: evalAt,
    });
    rise = rst.rise;
    set = rst.set;
    transit = rst.transit;
  }

  async function handleSetTarget() {
    if (raHours === null || decDeg === null) return;
    setSetting(true);
    setSetOk(null);
    try {
      await api.setGoto(raHours * 15, decDeg);
      setSetOk("ok");
      onTargetSet?.();
    } catch {
      setSetOk("error");
    } finally {
      setSetting(false);
      setTimeout(() => setSetOk(null), 2500);
    }
  }

  const paragraphs = object.description
    ? object.description.split(/\n\n+/).filter((p) => p.trim().length > 0)
    : [];

  return (
    <Card className="px-4 py-3 gap-3 text-sm">
      <div className="flex items-baseline justify-between gap-2">
        <div className="min-w-0">
          <div className="font-mono text-base">{object.designation}</div>
          <div className="text-muted-foreground truncate">{object.name}</div>
        </div>
        <span className="text-xs text-muted-foreground shrink-0">
          {object.subtype ?? object.type}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
        <Fact label="RA" value={object.rightAscension} mono />
        <Fact label="Dec" value={object.declination} mono />
        <Fact
          label="Mag"
          value={typeof object.magnitude === "number" ? object.magnitude.toFixed(1) : "—"}
        />
        <Fact label="Constellation" value={object.constellation} />
        <Fact
          label="Alt"
          value={altDeg !== null ? `${Math.round(altDeg)}°` : "—"}
        />
        <Fact
          label="Az"
          value={azDeg !== null ? azimuthCompass(azDeg) : "—"}
        />
        <Fact label="Rises" value={formatTimeLocal(rise)} />
        <Fact label="Transit" value={formatTimeLocal(transit)} />
        <Fact label="Sets" value={formatTimeLocal(set)} />
        <Fact
          label="Equipment"
          value={equipmentLabel(object.minEquipment)}
        />
        <Fact label="LP" value={object.lpTolerance} />
        <Fact label="Reward" value={object.visualReward} />
      </div>

      {paragraphs.length > 0 && (
        <div className="flex flex-col gap-2">
          {paragraphs.map((para, i) => (
            <p
              key={i}
              className="text-xs text-muted-foreground leading-relaxed"
            >
              {para}
            </p>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2 mt-1">
        <Button
          size="sm"
          onClick={handleSetTarget}
          disabled={setting || raHours === null || decDeg === null}
        >
          {setting ? "Setting…" : "Set as target"}
        </Button>
        <a
          href={buddyUrl(object.id)}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          Full description <ExternalLink className="w-3 h-3" />
        </a>
        {setOk === "ok" && (
          <span className="text-xs text-primary ml-auto">Target set</span>
        )}
        {setOk === "error" && (
          <span className="text-xs text-destructive ml-auto">Failed</span>
        )}
      </div>
    </Card>
  );
}

function Fact({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <>
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground self-center">
        {label}
      </span>
      <span className={cn("text-foreground", mono && "font-mono tabular-nums")}>
        {value}
      </span>
    </>
  );
}

function equipmentLabel(eq: string): string {
  return ({
    "naked-eye":         "Naked eye",
    "binoculars":        "Binoculars",
    "small-telescope":   "Small scope",
    "medium-telescope":  "Medium scope",
    "large-telescope":   "Large scope",
  } as Record<string, string>)[eq] ?? eq;
}
