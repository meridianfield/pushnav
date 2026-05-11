import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { ManualEntry as ManualEntryT } from "@/lib/catalogTypes";

interface Props {
  current: ManualEntryT | null;
  onSubmit: (entry: ManualEntryT) => void;
  onClear: () => void;
}

function raDegToHms(deg: number): { h: string; m: string; s: string } {
  const total = deg / 15;
  const h = Math.floor(total);
  const mFloat = (total - h) * 60;
  const m = Math.floor(mFloat);
  const s = (mFloat - m) * 60;
  return { h: String(h), m: String(m), s: s.toFixed(2) };
}

function decDegToDms(deg: number): { sign: Sign; d: string; m: string; s: string } {
  const sign: Sign = deg < 0 ? "-" : "+";
  const abs = Math.abs(deg);
  const d = Math.floor(abs);
  const mFloat = (abs - d) * 60;
  const m = Math.floor(mFloat);
  const s = (mFloat - m) * 60;
  return { sign, d: String(d), m: String(m), s: s.toFixed(2) };
}

type Sign = "+" | "-";

// Strip everything that isn't a digit or decimal point, and keep only the
// first decimal point so users can't accidentally type "5..3".
function digitsOnly(raw: string): string {
  const cleaned = raw.replace(/[^0-9.]/g, "");
  const i = cleaned.indexOf(".");
  if (i === -1) return cleaned;
  return cleaned.slice(0, i + 1) + cleaned.slice(i + 1).replace(/\./g, "");
}

export function ManualEntry({ current, onSubmit, onClear }: Props) {
  const initRa = current
    ? raDegToHms(current.ra_deg)
    : { h: "", m: "", s: "" };
  const initDec = current
    ? decDegToDms(current.dec_deg)
    : { sign: "+" as Sign, d: "", m: "", s: "" };

  const [raH, setRaH] = useState(initRa.h);
  const [raM, setRaM] = useState(initRa.m);
  const [raS, setRaS] = useState(initRa.s);
  const [decSign, setDecSign] = useState<Sign>(initDec.sign);
  const [decD, setDecD] = useState(initDec.d);
  const [decM, setDecM] = useState(initDec.m);
  const [decS, setDecS] = useState(initDec.s);
  const [error, setError] = useState<string | null>(null);

  function apply() {
    setError(null);
    const h = parseFloat(raH || "0");
    const m = parseFloat(raM || "0");
    const s = parseFloat(raS || "0");
    if (
      ![h, m, s].every(Number.isFinite)
      || h < 0 || h >= 24
      || m < 0 || m >= 60
      || s < 0 || s >= 60
    ) {
      setError("RA out of range. H must be 0–23, M and S must be 0–59.");
      return;
    }
    const dd = parseFloat(decD || "0");
    const dm = parseFloat(decM || "0");
    const ds = parseFloat(decS || "0");
    if (
      ![dd, dm, ds].every(Number.isFinite)
      || dd < 0 || dd > 90
      || dm < 0 || dm >= 60
      || ds < 0 || ds >= 60
    ) {
      setError("Dec out of range. D must be 0–90, M and S must be 0–59.");
      return;
    }
    const decAbs = dd + dm / 60 + ds / 3600;
    if (decAbs > 90) {
      setError("Dec exceeds ±90°.");
      return;
    }
    const ra_deg = (h + m / 60 + s / 3600) * 15;
    const dec_deg = decSign === "-" ? -decAbs : decAbs;
    onSubmit({ source: "manual", ra_deg, dec_deg });
  }

  function reset() {
    setRaH(""); setRaM(""); setRaS("");
    setDecSign("+"); setDecD(""); setDecM(""); setDecS("");
    setError(null);
  }

  const numCls = "h-7 w-12 text-xs font-mono text-center";
  const secCls = "h-7 w-16 text-xs font-mono text-center";
  const unit = "text-muted-foreground";

  return (
    <div className="flex flex-col gap-2 text-xs">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
        Manual coordinates (J2000)
      </div>

      <div className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-1 items-center">
        <span className={unit}>RA</span>
        <div className="flex items-center gap-1">
          <Input value={raH} onChange={(e) => setRaH(digitsOnly(e.target.value))}
                 inputMode="decimal" placeholder="hh" className={numCls} aria-label="RA hours" />
          <span className={unit}>h</span>
          <Input value={raM} onChange={(e) => setRaM(digitsOnly(e.target.value))}
                 inputMode="decimal" placeholder="mm" className={numCls} aria-label="RA minutes" />
          <span className={unit}>m</span>
          <Input value={raS} onChange={(e) => setRaS(digitsOnly(e.target.value))}
                 inputMode="decimal" placeholder="ss.s" className={secCls} aria-label="RA seconds" />
          <span className={unit}>s</span>
        </div>

        <span className={unit}>Dec</span>
        <div className="flex items-center gap-1">
          <Button type="button" size="sm" variant="outline"
                  className="h-7 w-7 p-0 font-mono"
                  onClick={() => setDecSign(decSign === "+" ? "-" : "+")}
                  aria-label="Toggle Dec sign">
            {decSign === "+" ? "+" : "−"}
          </Button>
          <Input value={decD} onChange={(e) => setDecD(digitsOnly(e.target.value))}
                 inputMode="decimal" placeholder="dd" className={numCls} aria-label="Dec degrees" />
          <span className={unit}>°</span>
          <Input value={decM} onChange={(e) => setDecM(digitsOnly(e.target.value))}
                 inputMode="decimal" placeholder="mm" className={numCls} aria-label="Dec minutes" />
          <span className={unit}>'</span>
          <Input value={decS} onChange={(e) => setDecS(digitsOnly(e.target.value))}
                 inputMode="decimal" placeholder="ss.s" className={secCls} aria-label="Dec seconds" />
          <span className={unit}>"</span>
        </div>
      </div>

      {error && <p className="text-destructive">{error}</p>}

      <div className="flex gap-2 mt-1">
        <Button size="sm" onClick={apply}>Use these coordinates</Button>
        <Button size="sm" variant="ghost"
                onClick={() => { reset(); onClear(); }}>
          Clear
        </Button>
      </div>
    </div>
  );
}
