import { useMemo } from "react";
import * as THREE from "three";
import { Edges, Line, OrbitControls } from "@react-three/drei";
import { HemisphereGrid } from "./HemisphereGrid";
import { Marker } from "./Marker";
import type { ThemeColors } from "./types";

const RADIUS = 2;
const SCOPE_LENGTH = RADIUS * 0.3;
const SCOPE_RADIUS = 0.1;

function altAzTo3D(altDeg: number, azDeg: number, radius = RADIUS) {
  const alt = altDeg * (Math.PI / 180);
  const az = -azDeg * (Math.PI / 180);
  return new THREE.Vector3(
    radius * Math.cos(alt) * Math.sin(az),
    radius * Math.sin(alt),
    radius * Math.cos(alt) * Math.cos(az),
  );
}

interface Pos {
  altDeg: number;
  azDeg: number;
}

interface Props {
  pointing: Pos | null;
  target: (Pos & { label?: string }) | null;
  colors: ThemeColors;
}

function Telescope({ direction, color }: { direction: THREE.Vector3; color: string }) {
  // Cylinder is built along the local Y axis by default; rotate so Y aligns
  // with the pointing direction, then translate to sit between origin and
  // SCOPE_LENGTH along that direction.
  const { position, quaternion } = useMemo(() => {
    const dir = direction.clone().normalize();
    const center = dir.clone().multiplyScalar(SCOPE_LENGTH / 2);
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
    return { position: center, quaternion: q };
  }, [direction]);

  return (
    <mesh position={position} quaternion={quaternion}>
      <cylinderGeometry args={[SCOPE_RADIUS, SCOPE_RADIUS, SCOPE_LENGTH, 16]} />
      <meshBasicMaterial color={color} transparent opacity={0.25} />
      <Edges threshold={30} color={color} />
    </mesh>
  );
}

export function SkyDomeCanvas({ pointing, target, colors }: Props) {
  const pointingVec =
    pointing && pointing.altDeg >= 0
      ? altAzTo3D(pointing.altDeg, pointing.azDeg)
      : null;
  const targetVec =
    target && target.altDeg >= 0
      ? altAzTo3D(target.altDeg, target.azDeg)
      : null;

  return (
    <>
      <OrbitControls
        enableZoom={true}
        enablePan={false}
        minDistance={3.5}
        maxDistance={8}
        minPolarAngle={0}
        maxPolarAngle={Math.PI / 2}
        rotateSpeed={0.5}
      />
      <ambientLight intensity={0.5} />
      <HemisphereGrid colors={colors} />

      {targetVec && (
        <Line
          points={[[0, 0, 0], [targetVec.x, targetVec.y, targetVec.z]]}
          color={colors.line}
          lineWidth={1.5}
          dashed
          dashSize={0.1}
          gapSize={0.06}
        />
      )}
      {pointingVec && (
        <>
          <Line
            points={[[0, 0, 0], [pointingVec.x, pointingVec.y, pointingVec.z]]}
            color={colors.line}
            lineWidth={1.5}
          />
          <Telescope direction={pointingVec} color={colors.line} />
        </>
      )}

      {pointing && (
        <Marker
          altDeg={pointing.altDeg}
          azDeg={pointing.azDeg}
          color={colors.pointing}
          size={0.03}
        />
      )}
      {target && (
        <Marker
          altDeg={target.altDeg}
          azDeg={target.azDeg}
          color={colors.target}
          label={target.label}
          size={0.04}
        />
      )}
    </>
  );
}
