import type { EnginePayload } from "@/lib/types";

interface Props {
  state: EnginePayload;
}

/**
 * Coordinate cross axes through the sync-offset origin, rotated by
 * finder_rotation. Mirrors the DPG _draw_coordinate_axes function in
 * window.py (1227-1300).
 */
export function AxesOverlay({ state }: Props) {
  if (!["CALIBRATE", "WARMING_UP", "TRACKING"].includes(state.state)) return null;
  if (!state.pointing.valid) return null;
  if (state.failures >= 3) return null;

  const cx = state.origin_x;
  const cy = state.origin_y;
  const phi = (state.finder_rotation * Math.PI) / 180;
  const upDx = Math.sin(phi);
  const upDy = -Math.cos(phi);
  const rightDx = Math.cos(phi);
  const rightDy = Math.sin(phi);

  const halfDiag = Math.sqrt(state.image_w ** 2 + state.image_h ** 2) / 2;
  const labelDist = 200;

  const labels = [
    { text: "UP",    x: cx - rightDx * labelDist, y: cy - rightDy * labelDist },
    { text: "DOWN",  x: cx + rightDx * labelDist, y: cy + rightDy * labelDist },
    { text: "RIGHT", x: cx + upDx * labelDist,    y: cy + upDy * labelDist },
    { text: "LEFT",  x: cx - upDx * labelDist,    y: cy - upDy * labelDist },
  ];

  return (
    <g stroke="rgba(180, 35, 35, 0.95)" fill="rgba(255, 70, 70, 0.86)">
      {/* Cross axis 1 (mount-up direction) — solid, darker so it's not
          confused with the marching-ants nav line. */}
      <line
        x1={cx - rightDx * halfDiag} y1={cy - rightDy * halfDiag}
        x2={cx + rightDx * halfDiag} y2={cy + rightDy * halfDiag}
        strokeWidth={1}
      />
      {/* Cross axis 2 (mount-right direction) */}
      <line
        x1={cx - upDx * halfDiag} y1={cy - upDy * halfDiag}
        x2={cx + upDx * halfDiag} y2={cy + upDy * halfDiag}
        strokeWidth={1}
      />
      {labels.map((l) => (
        <text
          key={l.text}
          x={l.x}
          y={l.y}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize={24}
          fontWeight="bold"
        >
          {l.text}
        </text>
      ))}
    </g>
  );
}
