import { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import { altAzFromRaDec } from "@/lib/astronomy";
import { useThemeColors } from "./useThemeColors";
import { SkyDomeCanvas } from "./SkyDomeCanvas";

interface Props {
  pointingRaDeg: number | null;
  pointingDecDeg: number | null;
  targetRaDeg: number | null;
  targetDecDeg: number | null;
  targetLabel?: string | null;
  latDeg: number | null;
  lonDeg: number | null;
  className?: string;
}

export function SkyDome({
  pointingRaDeg,
  pointingDecDeg,
  targetRaDeg,
  targetDecDeg,
  targetLabel,
  latDeg,
  lonDeg,
  className,
}: Props) {
  const colors = useThemeColors();
  const hasLocation = latDeg !== null && lonDeg !== null;
  const now = new Date();

  const pointing =
    hasLocation && pointingRaDeg !== null && pointingDecDeg !== null
      ? altAzFromRaDec({
          raHours: pointingRaDeg / 15,
          decDeg: pointingDecDeg,
          latDeg: latDeg!,
          lonDeg: lonDeg!,
          date: now,
        })
      : null;

  const target =
    hasLocation && targetRaDeg !== null && targetDecDeg !== null
      ? altAzFromRaDec({
          raHours: targetRaDeg / 15,
          decDeg: targetDecDeg,
          latDeg: latDeg!,
          lonDeg: lonDeg!,
          date: now,
        })
      : null;

  const targetBelowHorizon = target !== null && target.altDeg < 0;

  return (
    <div
      className={
        "relative w-full h-full min-h-[200px] rounded-md overflow-hidden border border-border/40 "
        + (className ?? "")
      }
    >
      <Canvas
        camera={{ position: [4, 2.5, 4], fov: 50, near: 0.1, far: 100 }}
        style={{ background: "transparent" }}
      >
        <Suspense fallback={null}>
          <SkyDomeCanvas
            pointing={pointing}
            target={
              target && !targetBelowHorizon
                ? { ...target, label: targetLabel ?? undefined }
                : null
            }
            colors={colors}
          />
        </Suspense>
      </Canvas>

      {!hasLocation && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="text-[11px] text-muted-foreground bg-background/70 px-2 py-1 rounded">
            Location info required
          </div>
        </div>
      )}

      {hasLocation && targetBelowHorizon && (
        <div className="absolute top-2 left-1/2 -translate-x-1/2 pointer-events-none">
          <div className="text-[11px] text-muted-foreground bg-background/70 px-2 py-1 rounded">
            Target below horizon
          </div>
        </div>
      )}
    </div>
  );
}
