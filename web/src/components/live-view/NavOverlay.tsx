import { useEffect, useState } from "react";
import type { EnginePayload, NavData } from "@/lib/types";

interface Props {
  state: EnginePayload;
}

const LOCKED_THRESHOLD_DEG = 0.15;

type Zone = "PUSH" | "CONVERGE" | "LOCKED";

function pickZone(nav: NavData): Zone {
  if (nav.in_fov && nav.separation_deg !== null && nav.separation_deg <= LOCKED_THRESHOLD_DEG) {
    return "LOCKED";
  }
  if (nav.in_fov) return "CONVERGE";
  return "PUSH";
}

function formatDist(sep: number | null): string {
  if (sep === null) return "--";
  if (sep >= 1.0) return `${sep.toFixed(1)}°`;
  return `${(sep * 60).toFixed(1)}'`;
}

/** Rounded background rect under text. */
function Pill({
  x, y, text, color = "rgba(255, 70, 70, 0.78)", bg = "rgba(40, 5, 5, 0.55)",
  fontSize = 22,
}: { x: number; y: number; text: string; color?: string; bg?: string; fontSize?: number }) {
  const w = text.length * (fontSize * 0.55) + 12;
  const h = fontSize + 6;
  return (
    <g>
      <rect x={x - w / 2} y={y - h / 2} width={w} height={h} rx={4} fill={bg} />
      <text x={x} y={y} textAnchor="middle" dominantBaseline="middle"
            fontSize={fontSize} fontWeight="bold" fill={color}>
        {text}
      </text>
    </g>
  );
}

/** PUSH/CONVERGE reticle: ring + cross arms */
function Reticle({
  cx, cy, color, ringR, armOuter, armInner, strokeW,
}: {
  cx: number; cy: number; color: string;
  ringR: number; armOuter: number; armInner: number; strokeW: number;
}) {
  return (
    <g stroke={color} strokeWidth={strokeW} fill="none">
      <circle cx={cx} cy={cy} r={ringR} />
      <line x1={cx - armOuter} y1={cy} x2={cx - armInner} y2={cy} />
      <line x1={cx + armInner} y1={cy} x2={cx + armOuter} y2={cy} />
      <line x1={cx} y1={cy - armOuter} x2={cx} y2={cy - armInner} />
      <line x1={cx} y1={cy + armInner} x2={cx} y2={cy + armOuter} />
    </g>
  );
}

/** Comet-style arrow: leading polygon at full opacity, fading ghosts trailing
 * behind. angleDeg is clockwise from up (the polygon's tip points to (0,-22)
 * in its local frame; +y in that frame is "behind" the tip). */
function CometArrow({
  cx, cy, angleDeg, color = "rgba(255, 100, 50, 1)",
}: { cx: number; cy: number; angleDeg: number; color?: string }) {
  const ghosts = [0, 1, 2, 3, 4];
  return (
    <g transform={`translate(${cx}, ${cy}) rotate(${angleDeg})`}>
      {ghosts
        .slice()
        .reverse()
        .map((i) => (
          <g
            key={i}
            transform={`translate(0 ${i * 9})`}
            style={{ opacity: 1 - i * 0.18 }}
          >
            <polygon
              points="0,-22 -11,0 -3,0 -3,18 3,18 3,0 11,0"
              fill={color}
            />
          </g>
        ))}
    </g>
  );
}

export function NavOverlay({ state }: Props) {
  const nav = state.nav;
  const [, setTick] = useState(0);

  useEffect(() => {
    if (!nav?.active) return;
    const id = setInterval(() => setTick((t) => (t + 1) % 1000), 50);
    return () => clearInterval(id);
  }, [nav?.active]);

  if (!nav || !nav.active) return null;

  const zone = pickZone(nav);
  const ox = state.origin_x;
  const oy = state.origin_y;

  if (zone === "PUSH") {
    if (nav.edge_x === null || nav.edge_y === null || nav.edge_angle_deg === null) {
      return null;
    }
    const angleRad = (nav.edge_angle_deg * Math.PI) / 180;
    // Arrow tip 68px inward from edge — same as DPG behavior
    const tipX = nav.edge_x - Math.sin(angleRad) * 68;
    const tipY = nav.edge_y + Math.cos(angleRad) * 68;
    // Perpendicular to the push direction (eyepiece → comet tip), used to
    // place the distance label off to one side so it doesn't overlap the
    // arrow body.
    const dx = tipX - ox;
    const dy = tipY - oy;
    const len = Math.hypot(dx, dy) || 1;
    const perpX = -dy / len;
    const perpY = dx / len;
    const labelOffset = 38;
    const labelX = tipX + perpX * labelOffset;
    const labelY = tipY + perpY * labelOffset;
    return (
      <g>
        <Reticle cx={ox} cy={oy} color="rgba(120, 25, 25, 0.63)"
                 ringR={12} armInner={4} armOuter={20} strokeW={1} />
        {/* Guide line extends all the way to the frame edge, not just to
            the comet tip — the comet sits on the line near the edge. */}
        <line x1={ox} y1={oy} x2={nav.edge_x} y2={nav.edge_y}
              stroke="rgba(255, 100, 50, 0.9)" strokeWidth={2}
              strokeDasharray="8 6"
              className="pushnav-marching-ants" />
        <CometArrow cx={tipX} cy={tipY}
                    angleDeg={nav.edge_angle_deg} />
        <Pill x={labelX} y={labelY}
              text={formatDist(nav.separation_deg)}
              color="rgba(255, 100, 50, 1)" />
      </g>
    );
  }

  if (zone === "CONVERGE") {
    if (nav.pixel_x === null || nav.pixel_y === null) return null;
    const tx = nav.pixel_x;
    const ty = nav.pixel_y;
    // 0.15° lock-zone ring
    const scale = state.image_w / (2 * Math.tan((state.fov_h_deg / 2) * (Math.PI / 180)));
    const lockR = Math.tan(LOCKED_THRESHOLD_DEG * (Math.PI / 180)) * scale;
    // Direction from eyepiece reticle to target — in screen coords, "up" is -y,
    // so atan2(dx, -dy) gives a clockwise-from-up angle in degrees.
    const dx = tx - ox;
    const dy = ty - oy;
    const len = Math.hypot(dx, dy) || 1;
    const arrowAngleDeg = (Math.atan2(dx, -dy) * 180) / Math.PI;
    // Perpendicular unit vector (one of two possible — pick whichever, labels
    // sit consistently on one side of the arrow). Rotated 90° CCW from
    // direction-to-target in screen coords.
    const perpX = -dy / len;
    const perpY = dx / len;
    const distLabelOffset = 38;
    const nameLabelOffset = 64;
    const distLabelX = tx + perpX * distLabelOffset;
    const distLabelY = ty + perpY * distLabelOffset;
    const nameLabelX = tx + perpX * nameLabelOffset;
    const nameLabelY = ty + perpY * nameLabelOffset;
    return (
      <g>
        <Reticle cx={ox} cy={oy} color="rgba(200, 50, 50, 0.78)"
                 ringR={14} armInner={5} armOuter={24} strokeW={2} />
        <circle cx={ox} cy={oy} r={lockR}
                stroke="rgba(200, 50, 50, 0.24)" strokeWidth={1} fill="none" />
        <line x1={ox} y1={oy} x2={tx} y2={ty}
              stroke="rgba(255, 70, 70, 0.78)" strokeWidth={1}
              strokeDasharray="8 6"
              className="pushnav-marching-ants" />
        {/* Single arrow at target tip, oriented along the eyepiece→target
            direction. Outer <g>'s translate+rotate animate together so the
            arrow glides and re-aims smoothly between WS updates. */}
        <g
          style={{
            transform: `translate(${tx}px, ${ty}px) rotate(${arrowAngleDeg}deg)`,
            transition: "transform 100ms linear",
          }}
        >
          <polygon
            points="0,-22 -11,0 -3,0 -3,18 3,18 3,0 11,0"
            fill="rgba(255, 70, 70, 0.86)"
          />
        </g>
        <Pill x={distLabelX} y={distLabelY}
              text={formatDist(nav.separation_deg)}
              color="rgba(255, 70, 70, 0.86)" />
        {nav.target_name && (
          <Pill x={nameLabelX} y={nameLabelY} text={nav.target_name}
                color="rgba(255, 70, 70, 0.86)" />
        )}
      </g>
    );
  }

  // LOCKED — pulsing concentric rings + center dot + ON TARGET text
  const t = performance.now() / 1000;
  const pulse = 0.7 + 0.3 * (0.5 + 0.5 * Math.sin((t * 2 * Math.PI) / 1.2));
  const alpha = pulse;
  const color = `rgba(255, 120, 80, ${alpha.toFixed(3)})`;
  return (
    <g>
      <circle cx={ox} cy={oy} r={20} stroke={color} strokeWidth={2} fill="none" />
      <circle cx={ox} cy={oy} r={14} stroke={color} strokeWidth={3} fill="none" />
      <circle cx={ox} cy={oy} r={8}  stroke={color} strokeWidth={2} fill="none" />
      <circle cx={ox} cy={oy} r={4}  fill={color} />
      {nav.target_name && (
        <Pill x={ox} y={oy - 45} text={nav.target_name} color={color} />
      )}
      <Pill x={ox} y={oy + 45} text="ON TARGET" color={color} />
    </g>
  );
}
