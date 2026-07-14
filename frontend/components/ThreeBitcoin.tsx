"use client";

import { useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Text, RoundedBox } from "@react-three/drei";
import * as THREE from "three";

function createCircuitTexture() {
  const size = 1024;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;

  // Gold radial base
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 40, size / 2, size / 2, size / 2);
  gradient.addColorStop(0, "#FFDF8C");
  gradient.addColorStop(0.45, "#F7931A");
  gradient.addColorStop(0.85, "#B45309");
  gradient.addColorStop(1, "#78350F");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);

  // Circuit rings
  ctx.strokeStyle = "rgba(255, 255, 255, 0.22)";
  ctx.lineWidth = 4;
  for (let r = 140; r < 420; r += 45) {
    ctx.beginPath();
    ctx.arc(size / 2, size / 2, r, 0, Math.PI * 2);
    ctx.stroke();
  }

  // Radial circuit traces
  for (let i = 0; i < 24; i++) {
    const angle = (i / 24) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(size / 2 + Math.cos(angle) * 160, size / 2 + Math.sin(angle) * 160);
    ctx.lineTo(size / 2 + Math.cos(angle) * 400, size / 2 + Math.sin(angle) * 400);
    ctx.stroke();
  }

  // Small nodes
  ctx.fillStyle = "rgba(255, 255, 255, 0.35)";
  for (let i = 0; i < 36; i++) {
    const angle = (i / 36) * Math.PI * 2;
    const r = 280 + (i % 3) * 70;
    ctx.beginPath();
    ctx.arc(size / 2 + Math.cos(angle) * r, size / 2 + Math.sin(angle) * r, 8, 0, Math.PI * 2);
    ctx.fill();
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.anisotropy = 16;
  return texture;
}

function Coin({ hovered, onHover }: { hovered: boolean; onHover: (v: boolean) => void }) {
  const groupRef = useRef<THREE.Group>(null);
  const circuitTexture = useMemo(() => createCircuitTexture(), []);

  useFrame((state, delta) => {
    if (!groupRef.current) return;
    const baseSpeed = 1.0;
    const speed = hovered ? baseSpeed * 2.8 : baseSpeed;
    groupRef.current.rotation.y += delta * speed;
    groupRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.5) * 0.12;
    groupRef.current.position.y = Math.sin(state.clock.elapsedTime * 0.8) * 0.08;
  });

  const goldMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        map: circuitTexture,
        color: 0xffffff,
        metalness: 0.95,
        roughness: 0.18,
        emissive: new THREE.Color(hovered ? "#F7931A" : "#000000"),
        emissiveIntensity: hovered ? 0.25 : 0,
      }),
    [circuitTexture, hovered]
  );

  const rimMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#B45309",
        metalness: 1,
        roughness: 0.15,
        emissive: new THREE.Color(hovered ? "#FBBF24" : "#000000"),
        emissiveIntensity: hovered ? 0.15 : 0,
      }),
    [hovered]
  );

  const ringMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#FDE68A",
        metalness: 0.9,
        roughness: 0.25,
        transparent: true,
        opacity: 0.75,
        emissive: new THREE.Color(hovered ? "#FDE68A" : "#000000"),
        emissiveIntensity: hovered ? 0.4 : 0,
      }),
    [hovered]
  );

  return (
    <group
      ref={groupRef}
      onPointerOver={() => onHover(true)}
      onPointerOut={() => onHover(false)}
      scale={hovered ? 1.06 : 1}
    >
      {/* Milled outer edge */}
      <mesh>
        <cylinderGeometry args={[1.35, 1.35, 0.22, 96]} />
        <meshStandardMaterial color="#92400E" metalness={1} roughness={0.2} />
      </mesh>

      {/* Top and bottom faces with circuitry texture */}
      <mesh position={[0, 0.11, 0]} rotation={[0, 0, 0]} material={goldMaterial}>
        <cylinderGeometry args={[1.28, 1.28, 0.02, 96]} />
      </mesh>
      <mesh position={[0, -0.11, 0]} rotation={[0, 0, 0]} material={goldMaterial}>
        <cylinderGeometry args={[1.28, 1.28, 0.02, 96]} />
      </mesh>

      {/* Outer rim ring */}
      <mesh position={[0, 0.12, 0]} rotation={[Math.PI / 2, 0, 0]} material={rimMaterial}>
        <ringGeometry args={[1.15, 1.3, 96]} />
      </mesh>
      <mesh position={[0, -0.12, 0]} rotation={[Math.PI / 2, 0, 0]} material={rimMaterial}>
        <ringGeometry args={[1.15, 1.3, 96]} />
      </mesh>

      {/* Inner circuit ring */}
      <mesh position={[0, 0.125, 0]} rotation={[Math.PI / 2, 0, 0]} material={ringMaterial}>
        <ringGeometry args={[0.85, 1.05, 96]} />
      </mesh>
      <mesh position={[0, -0.125, 0]} rotation={[Math.PI / 2, 0, 0]} material={ringMaterial}>
        <ringGeometry args={[0.85, 1.05, 96]} />
      </mesh>

      {/* Bitcoin symbol */}
      <Text
        position={[0, 0.14, 0.65]}
        fontSize={1.05}
        color="#FFFFFF"
        anchorX="center"
        anchorY="middle"
        material={new THREE.MeshStandardMaterial({
          color: "#ffffff",
          metalness: 0.8,
          roughness: 0.2,
          emissive: new THREE.Color(hovered ? "#FFFFFF" : "#000000"),
          emissiveIntensity: hovered ? 0.3 : 0,
        })}
      >
        ₿
      </Text>
      <Text
        position={[0, -0.14, 0.65]}
        fontSize={1.05}
        color="#FFFFFF"
        anchorX="center"
        anchorY="middle"
        rotation={[Math.PI, 0, 0]}
        material={new THREE.MeshStandardMaterial({
          color: "#ffffff",
          metalness: 0.8,
          roughness: 0.2,
          emissive: new THREE.Color(hovered ? "#FFFFFF" : "#000000"),
          emissiveIntensity: hovered ? 0.3 : 0,
        })}
      >
        ₿
      </Text>

      {/* BITCOIN rim text */}
      {"BITCOIN".split("").map((letter, i) => {
        const angle = (i / 7) * Math.PI * 2;
        return (
          <Text
            key={i}
            position={[Math.cos(angle) * 1.32, 0.12, Math.sin(angle) * 1.32]}
            rotation={[-Math.PI / 2, -angle + Math.PI / 2, 0]}
            fontSize={0.16}
            color="#FDE68A"
            anchorX="center"
            anchorY="middle"
          >
            {letter}
          </Text>
        );
      })}
    </group>
  );
}

function GoldBars() {
  const groupRef = useRef<THREE.Group>(null);
  useFrame((state) => {
    if (!groupRef.current) return;
    groupRef.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.35) * 0.08;
    groupRef.current.position.y = -1.8 + Math.sin(state.clock.elapsedTime * 0.6) * 0.04;
  });

  return (
    <group ref={groupRef} position={[-2.2, 0, 0]}>
      {[0, 0.15, 0.3].map((y, i) => (
        <mesh key={i} position={[0, y, i * 0.12 - 0.12]} castShadow receiveShadow>
          <RoundedBox args={[1.5, 0.45, 0.38]} radius={0.05} smoothness={4}>
            <meshStandardMaterial
              color="#E5C45A"
              metalness={1}
              roughness={0.12}
              emissive="#B8860B"
              emissiveIntensity={0.15 + i * 0.05}
            />
          </RoundedBox>
        </mesh>
      ))}
    </group>
  );
}

function TrendRibbon({ color = "#16A34A" }: { color?: string }) {
  const ref = useRef<THREE.Mesh>(null);
  const points = useMemo(() => {
    const arr: THREE.Vector3[] = [];
    for (let i = 0; i <= 40; i++) {
      arr.push(new THREE.Vector3((i - 20) * 0.12, Math.sin(i * 0.4) * 0.25, 0));
    }
    return arr;
  }, []);

  useFrame((state) => {
    if (!ref.current) return;
    const positions = ref.current.geometry.attributes.position.array as Float32Array;
    for (let i = 0; i <= 40; i++) {
      const y = Math.sin(i * 0.4 + state.clock.elapsedTime * 1.5) * 0.28 + Math.sin(state.clock.elapsedTime * 0.7) * 0.1;
      positions[i * 3 + 1] = y;
    }
    ref.current.geometry.attributes.position.needsUpdate = true;
    ref.current.position.y = 1.2 + Math.sin(state.clock.elapsedTime * 0.5) * 0.05;
  });

  const curve = useMemo(() => new THREE.CatmullRomCurve3(points), [points]);

  return (
    <mesh ref={ref}>
      <tubeGeometry args={[curve, 64, 0.035, 12, false]} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={0.6}
        metalness={0.3}
        roughness={0.4}
        transparent
        opacity={0.9}
      />
    </mesh>
  );
}

export default function ThreeBitcoin({ className }: { className?: string }) {
  const [hovered, setHovered] = useState(false);
  return (
    <div className={className}>
      <Canvas camera={{ position: [0, 0.4, 5.8], fov: 42 }} shadows dpr={[1, 2]}>
        <ambientLight intensity={0.7} />
        <directionalLight position={[4, 6, 4]} intensity={1.6} castShadow color="#FFF7ED" />
        <directionalLight position={[-4, 2, -2]} intensity={0.8} color="#E0E7FF" />
        <pointLight position={[-3, 3, 2]} intensity={1.3} color="#FDE68A" distance={10} />
        <pointLight position={[3, -2, 2]} intensity={0.9} color="#818CF8" distance={10} />
        <pointLight position={[0, 2, -3]} intensity={0.6} color="#FFFFFF" distance={10} />

        <Coin hovered={hovered} onHover={setHovered} />
        <GoldBars />
        <TrendRibbon color="#16A34A" />
        <TrendRibbon color="#DC2626" />
      </Canvas>
    </div>
  );
}
