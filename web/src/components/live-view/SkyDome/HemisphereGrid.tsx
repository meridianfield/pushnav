import { useMemo } from "react";
import * as THREE from "three";
import { Html, Line } from "@react-three/drei";
import type { ThemeColors } from "./types";

const RADIUS = 2;
const ALTITUDE_STEPS = [15, 30, 45, 60, 75];
const AZIMUTH_DIRECTIONS = [
  { az: 0, label: "N" },
  { az: 22.5, label: "" },
  { az: 45, label: "NE" },
  { az: 67.5, label: "" },
  { az: 90, label: "E" },
  { az: 112.5, label: "" },
  { az: 135, label: "SE" },
  { az: 157.5, label: "" },
  { az: 180, label: "S" },
  { az: 202.5, label: "" },
  { az: 225, label: "SW" },
  { az: 247.5, label: "" },
  { az: 270, label: "W" },
  { az: 292.5, label: "" },
  { az: 315, label: "NW" },
  { az: 337.5, label: "" },
];

function altAzTo3D(altDeg: number, azDeg: number, radius: number) {
  const alt = altDeg * (Math.PI / 180);
  const az = -azDeg * (Math.PI / 180);
  return new THREE.Vector3(
    radius * Math.cos(alt) * Math.sin(az),
    radius * Math.sin(alt),
    radius * Math.cos(alt) * Math.cos(az),
  );
}

function createAltitudeCircle(altDeg: number, radius: number): THREE.Vector3[] {
  const points: THREE.Vector3[] = [];
  const segments = 64;
  for (let i = 0; i <= segments; i++) {
    const azDeg = (i / segments) * 360;
    points.push(altAzTo3D(altDeg, azDeg, radius));
  }
  return points;
}

function createAzimuthLine(azDeg: number, radius: number): THREE.Vector3[] {
  const points: THREE.Vector3[] = [];
  const segments = 16;
  for (let i = 0; i <= segments; i++) {
    const altDeg = (i / segments) * 90;
    points.push(altAzTo3D(altDeg, azDeg, radius));
  }
  return points;
}

const LABEL_STYLE: React.CSSProperties = {
  fontSize: 11,
  lineHeight: 1,
  whiteSpace: "nowrap",
  pointerEvents: "none",
  userSelect: "none",
  textShadow: "0 0 4px rgba(0,0,0,0.8)",
};

export function HemisphereGrid({ colors }: { colors: ThemeColors }) {
  const altitudeCircles = useMemo(
    () => ALTITUDE_STEPS.map((alt) => createAltitudeCircle(alt, RADIUS)),
    [],
  );
  const azimuthLines = useMemo(
    () => AZIMUTH_DIRECTIONS.map((dir) => createAzimuthLine(dir.az, RADIUS)),
    [],
  );
  const horizonCircle = useMemo(() => createAltitudeCircle(0, RADIUS), []);

  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]}>
        <circleGeometry args={[RADIUS, 64]} />
        <meshBasicMaterial color={colors.ground} transparent opacity={0.25} side={2} />
      </mesh>

      <Line
        points={horizonCircle}
        color={colors.horizon}
        lineWidth={1}
        transparent
        opacity={0.5}
      />

      {altitudeCircles.map((points, i) => (
        <Line
          key={`alt-${ALTITUDE_STEPS[i]}`}
          points={points}
          color={colors.gridLines}
          lineWidth={1}
          transparent
          opacity={0.35}
        />
      ))}

      {azimuthLines.map((points, i) => (
        <Line
          key={`az-${AZIMUTH_DIRECTIONS[i].az}`}
          points={points}
          color={colors.gridLines}
          lineWidth={1}
          transparent
          opacity={0.35}
        />
      ))}

      {AZIMUTH_DIRECTIONS.filter((d) => d.label !== "").map((dir) => {
        const pos = altAzTo3D(0, dir.az, RADIUS + 0.2);
        return (
          <Html
            key={`label-${dir.label}`}
            position={[pos.x, 0.02, pos.z]}
            center
            pointerEvents="none"
          >
            <div style={{ ...LABEL_STYLE, color: colors.gridLabels }}>
              {dir.label}
            </div>
          </Html>
        );
      })}

      <Html position={[0, RADIUS + 0.15, 0]} center pointerEvents="none">
        <div style={{ ...LABEL_STYLE, color: colors.gridLabels }}>Z</div>
      </Html>
    </group>
  );
}
