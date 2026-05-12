import * as THREE from "three";
import { Html } from "@react-three/drei";

const RADIUS = 2;

function altAzTo3D(altDeg: number, azDeg: number, radius: number) {
  const alt = altDeg * (Math.PI / 180);
  const az = -azDeg * (Math.PI / 180);
  return new THREE.Vector3(
    radius * Math.cos(alt) * Math.sin(az),
    radius * Math.sin(alt),
    radius * Math.cos(alt) * Math.cos(az),
  );
}

interface MarkerProps {
  altDeg: number;
  azDeg: number;
  color: string;
  label?: string;
  size?: number;
}

export function Marker({ altDeg, azDeg, color, label, size = 0.06 }: MarkerProps) {
  if (altDeg < 0) return null;
  const pos = altAzTo3D(altDeg, azDeg, RADIUS);

  return (
    <group position={[pos.x, pos.y, pos.z]}>
      <mesh>
        <sphereGeometry args={[size, 16, 16]} />
        <meshBasicMaterial color={color} />
      </mesh>
      {label && (
        <Html position={[0, size + 0.05, 0]} center pointerEvents="none">
          <div
            style={{
              color,
              fontSize: 11,
              lineHeight: 1,
              whiteSpace: "nowrap",
              pointerEvents: "none",
              transform: "translateY(-100%)",
              textShadow: "0 0 4px rgba(0,0,0,0.8)",
            }}
          >
            {label}
          </div>
        </Html>
      )}
    </group>
  );
}
