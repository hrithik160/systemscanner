import React, { useMemo, useRef, useState, useEffect } from 'react';
import * as THREE from 'three';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, Stars, Grid, Html } from '@react-three/drei';
import { type OrbitControls as OrbitControlsType } from 'three-stdlib';
import { useReleaseStore } from '../store/releaseStore';
import { CNode, CEdge } from '../../../shared/types';
import {
  Crown,
  ShieldCheck,
  ShieldAlert,
  Radio,
  Eye,
  Compass,
  Zap,
  Boxes,
  GitBranch,
  Activity,
  Gauge,
  AudioWaveform,
  Wifi,
  WifiOff,
  Command,
  Sparkles,
  Shield,
  Layers,
  ChevronUp,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Move,
  Server,
  Database,
  Network,
  Crosshair,
  FileCode,
} from 'lucide-react';

/* -------------------------------------------------------------------------- */
/*                                3D CAMERA CONTROLLER                         */
/* -------------------------------------------------------------------------- */
type CameraPreset = 'overview' | 'topdown' | 'services' | 'entrypoints' | 'database';

interface NavigationAction {
  type: 'up' | 'down' | 'left' | 'right' | 'zoomIn' | 'zoomOut' | 'reset';
  ts: number;
}

interface CameraControlProps {
  preset: CameraPreset | null;
  selectedPos: [number, number, number] | null;
  onPresetDone: () => void;
  dragMode: 'orbit' | 'pan';
  navigationAction: NavigationAction | null;
}

const CameraController: React.FC<CameraControlProps> = ({
  preset,
  selectedPos,
  onPresetDone,
  dragMode,
  navigationAction,
}) => {
  const { camera } = useThree();
  const controlsRef = useRef<OrbitControlsType>(null);

  // Smooth camera repositioning on presets
  useEffect(() => {
    if (!preset) return;

    if (preset === 'overview') {
      camera.position.set(0, 16, 28);
      camera.lookAt(0, 0, 0);
      controlsRef.current?.target.set(0, 0, 0);
    } else if (preset === 'topdown') {
      camera.position.set(0, 36, 1);
      camera.lookAt(0, 0, 0);
      controlsRef.current?.target.set(0, 0, 0);
    } else if (preset === 'services') {
      camera.position.set(-12, 10, 18);
      camera.lookAt(-4, 0, 2);
      controlsRef.current?.target.set(-4, 0, 2);
    } else if (preset === 'entrypoints') {
      camera.position.set(-18, 8, 14);
      camera.lookAt(-12, 0, -2);
      controlsRef.current?.target.set(-12, 0, -2);
    } else if (preset === 'database') {
      camera.position.set(14, 8, 14);
      camera.lookAt(10, 0, 4);
      controlsRef.current?.target.set(10, 0, 4);
    }

    controlsRef.current?.update();
    onPresetDone();
  }, [preset, camera, onPresetDone]);

  // Center target when selected node changes
  const prevTargetRef = useRef<string | null>(null);
  useEffect(() => {
    if (selectedPos) {
      const key = selectedPos.join(',');
      if (prevTargetRef.current !== key) {
        prevTargetRef.current = key;
        controlsRef.current?.target.set(...selectedPos);
        controlsRef.current?.update();
      }
    }
  }, [selectedPos]);

  // Handle D-Pad / navigation buttons (Up, Down, Left, Right, Zoom In/Out, Reset)
  useEffect(() => {
    if (!navigationAction || !controlsRef.current) return;
    const ctrl = controlsRef.current;
    const step = 2.4;

    switch (navigationAction.type) {
      case 'up':
        camera.position.y += step;
        ctrl.target.y += step;
        break;
      case 'down':
        camera.position.y -= step;
        ctrl.target.y -= step;
        break;
      case 'left':
        camera.position.x -= step;
        ctrl.target.x -= step;
        break;
      case 'right':
        camera.position.x += step;
        ctrl.target.x += step;
        break;
      case 'zoomIn': {
        const dir = new THREE.Vector3().subVectors(camera.position, ctrl.target);
        dir.multiplyScalar(0.78);
        camera.position.copy(ctrl.target).add(dir);
        break;
      }
      case 'zoomOut': {
        const dir = new THREE.Vector3().subVectors(camera.position, ctrl.target);
        dir.multiplyScalar(1.25);
        camera.position.copy(ctrl.target).add(dir);
        break;
      }
      case 'reset':
        camera.position.set(0, 16, 28);
        ctrl.target.set(0, 0, 0);
        camera.lookAt(0, 0, 0);
        break;
    }
    ctrl.update();
  }, [navigationAction, camera]);

  // Keyboard navigation: W/S or ArrowUp/ArrowDown to move up/down; A/D or ArrowLeft/ArrowRight to move left/right
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) {
        return;
      }
      if (!controlsRef.current) return;
      const ctrl = controlsRef.current;
      const step = 2.0;

      if (e.key === 'ArrowUp' || e.key === 'w' || e.key === 'W') {
        e.preventDefault();
        e.stopPropagation();
        camera.position.y += step;
        ctrl.target.y += step;
        ctrl.update();
      } else if (e.key === 'ArrowDown' || e.key === 's' || e.key === 'S') {
        e.preventDefault();
        e.stopPropagation();
        camera.position.y -= step;
        ctrl.target.y -= step;
        ctrl.update();
      } else if (e.key === 'ArrowLeft' || e.key === 'a' || e.key === 'A') {
        e.preventDefault();
        e.stopPropagation();
        camera.position.x -= step;
        ctrl.target.x -= step;
        ctrl.update();
      } else if (e.key === 'ArrowRight' || e.key === 'd' || e.key === 'D') {
        e.preventDefault();
        e.stopPropagation();
        camera.position.x += step;
        ctrl.target.x += step;
        ctrl.update();
      } else if (e.key === 'q' || e.key === 'Q' || e.key === 'PageUp') {
        camera.position.y += step * 1.5;
        ctrl.target.y += step * 1.5;
        ctrl.update();
      } else if (e.key === 'e' || e.key === 'E' || e.key === 'PageDown') {
        camera.position.y -= step * 1.5;
        ctrl.target.y -= step * 1.5;
        ctrl.update();
      } else if (e.key === '+' || e.key === '=') {
        const dir = new THREE.Vector3().subVectors(camera.position, ctrl.target);
        dir.multiplyScalar(0.85);
        camera.position.copy(ctrl.target).add(dir);
        ctrl.update();
      } else if (e.key === '-' || e.key === '_') {
        const dir = new THREE.Vector3().subVectors(camera.position, ctrl.target);
        dir.multiplyScalar(1.15);
        camera.position.copy(ctrl.target).add(dir);
        ctrl.update();
      }
    };

    window.addEventListener('keydown', handleKeyDown, true);
    return () => window.removeEventListener('keydown', handleKeyDown, true);
  }, [camera]);

  return (
    <OrbitControls
      ref={controlsRef}
      enableDamping={true}
      dampingFactor={0.06}
      enablePan={true}
      enableZoom={true}
      enableRotate={true}
      panSpeed={1.5}
      rotateSpeed={0.8}
      zoomSpeed={1.2}
      minDistance={2}
      maxDistance={120}
      minPolarAngle={0.02}
      maxPolarAngle={Math.PI - 0.02}
      screenSpacePanning={true}
      mouseButtons={{
        LEFT: dragMode === 'pan' ? THREE.MOUSE.PAN : THREE.MOUSE.ROTATE,
        MIDDLE: THREE.MOUSE.DOLLY,
        RIGHT: THREE.MOUSE.PAN,
      }}
    />
  );
};

/* -------------------------------------------------------------------------- */
/*                                3D NODE OBJECT                              */
/* -------------------------------------------------------------------------- */
interface Node3DProps {
  node: CNode;
  position: [number, number, number];
  isSelected: boolean;
  isExecuting: boolean;
  onClick: (id: string) => void;
}

const CyberNodeObject: React.FC<Node3DProps> = ({
  node,
  position,
  isSelected,
  isExecuting,
  onClick,
}) => {
  const groupRef = useRef<THREE.Group>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  const ring2Ref = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);

  useFrame((state) => {
    if (!groupRef.current) return;
    const t = state.clock.getElapsedTime();
    const phase = position[0] * 0.35 + position[2] * 0.25;
    groupRef.current.position.y = position[1] + Math.sin(t * 1.5 + phase) * 0.16;

    if (ringRef.current) {
      ringRef.current.rotation.z = t * 0.85;
      ringRef.current.rotation.x = t * 0.45;
    }
    if (ring2Ref.current) {
      ring2Ref.current.rotation.z = -t * 1.1;
      ring2Ref.current.rotation.y = t * 0.65;
    }
  });

  const isCrown = !!node.is_crown_jewel;
  const isChanged = node.status === 'changed';
  const isFailing = node.status === 'failing';

  // Determine hardware mesh model based on node kind / label
  const labelLower = (node.label || node.id).toLowerCase();
  const isDb =
    labelLower.includes('db') ||
    labelLower.includes('data') ||
    labelLower.includes('sql') ||
    labelLower.includes('postgres') ||
    labelLower.includes('redis') ||
    node.kind === 'infra';
  const isIdentity =
    labelLower.includes('auth') ||
    labelLower.includes('jwt') ||
    labelLower.includes('token') ||
    labelLower.includes('iam') ||
    labelLower.includes('identity') ||
    labelLower.includes('guard');
  const isLaptop =
    labelLower.includes('laptop') ||
    labelLower.includes('client') ||
    labelLower.includes('dev') ||
    labelLower.includes('workstation') ||
    labelLower.includes('ui') ||
    node.kind === 'view';
  const isIoT =
    labelLower.includes('printer') ||
    labelLower.includes('iot') ||
    labelLower.includes('sensor');

  let mainColor = '#8b5cf6';
  let emissiveColor = '#8b5cf6';
  let emissiveIntensity = isSelected ? 1.7 : hovered ? 1.2 : 0.45;

  if (isExecuting) {
    mainColor = '#2563eb';
    emissiveColor = '#60a5fa';
    emissiveIntensity = 2.5;
  } else if (isCrown || isDb) {
    mainColor = isFailing ? '#ef4444' : '#fbbf24';
    emissiveColor = isFailing ? '#ef4444' : '#f59e0b';
    emissiveIntensity = isSelected ? 1.9 : 1.3;
  } else if (isFailing) {
    mainColor = '#ef4444';
    emissiveColor = '#ef4444';
    emissiveIntensity = 1.9;
  } else if (isChanged) {
    mainColor = '#06b6d4';
    emissiveColor = '#06b6d4';
    emissiveIntensity = 1.5;
  } else if (node.kind === 'sandbox' || node.kind === 'route') {
    mainColor = '#10b981';
    emissiveColor = '#10b981';
    emissiveIntensity = 1.4;
  } else if (node.kind === 'service') {
    mainColor = '#9333ea';
    emissiveColor = '#c084fc';
    emissiveIntensity = 1.3;
  }

  const renderShape = () => {
    // 1. Database Unit (Cylinder with torus accent bands)
    if (isDb && !isCrown) {
      return (
        <group>
          <mesh castShadow receiveShadow>
            <cylinderGeometry args={[0.72, 0.72, 1.4, 24]} />
            <meshStandardMaterial
              color={mainColor}
              emissive={emissiveColor}
              emissiveIntensity={emissiveIntensity}
              roughness={0.2}
              metalness={0.8}
            />
          </mesh>
          <mesh position={[0, 0.38, 0]}>
            <torusGeometry args={[0.75, 0.045, 12, 24]} />
            <meshBasicMaterial color="#ffffff" />
          </mesh>
          <mesh position={[0, -0.38, 0]}>
            <torusGeometry args={[0.75, 0.045, 12, 24]} />
            <meshBasicMaterial color="#ffffff" />
          </mesh>
        </group>
      );
    }

    // 2. Identity / Security (Octahedron crystal with dual gyroscopic rotating rings)
    if (isIdentity || isCrown) {
      return (
        <group>
          <mesh castShadow receiveShadow>
            <octahedronGeometry args={[0.88, 0]} />
            <meshStandardMaterial
              color={mainColor}
              emissive={emissiveColor}
              emissiveIntensity={emissiveIntensity}
              roughness={0.15}
              metalness={0.9}
            />
          </mesh>
          <mesh ref={ringRef}>
            <torusGeometry args={[1.25, 0.035, 12, 32]} />
            <meshBasicMaterial color={emissiveColor} />
          </mesh>
          <mesh ref={ring2Ref}>
            <torusGeometry args={[1.45, 0.025, 12, 32]} />
            <meshBasicMaterial color="#ffffff" />
          </mesh>
        </group>
      );
    }

    // 3. Client / Workstation
    if (isLaptop) {
      return (
        <group>
          <mesh position={[0, -0.35, 0]} castShadow receiveShadow>
            <boxGeometry args={[1.25, 0.16, 0.95]} />
            <meshStandardMaterial
              color="#170f2e"
              emissive={emissiveColor}
              emissiveIntensity={emissiveIntensity * 0.4}
              roughness={0.3}
              metalness={0.7}
            />
          </mesh>
          <mesh position={[0, 0.16, -0.22]} rotation={[-0.28, 0, 0]}>
            <boxGeometry args={[1.15, 0.85, 0.07]} />
            <meshStandardMaterial
              color={mainColor}
              emissive={emissiveColor}
              emissiveIntensity={emissiveIntensity}
              roughness={0.2}
              metalness={0.8}
            />
          </mesh>
        </group>
      );
    }

    // 4. IoT / Network Appliance
    if (isIoT) {
      return (
        <group>
          <mesh castShadow receiveShadow>
            <boxGeometry args={[0.92, 0.78, 0.92]} />
            <meshStandardMaterial
              color={mainColor}
              emissive={emissiveColor}
              emissiveIntensity={emissiveIntensity}
              roughness={0.3}
              metalness={0.7}
            />
          </mesh>
          <mesh position={[0.26, 0.62, 0.26]}>
            <cylinderGeometry args={[0.03, 0.03, 0.45, 12]} />
            <meshBasicMaterial color="#94a3b8" />
          </mesh>
          <mesh position={[0.26, 0.85, 0.26]}>
            <sphereGeometry args={[0.08, 12, 12]} />
            <meshBasicMaterial color={emissiveColor} />
          </mesh>
        </group>
      );
    }

    // 5. Server Tower / Rack (Chassis with drive bay indicators)
    return (
      <group>
        <mesh castShadow receiveShadow>
          <boxGeometry args={[0.95, 1.4, 0.95]} />
          <meshStandardMaterial
            color={mainColor}
            emissive={emissiveColor}
            emissiveIntensity={emissiveIntensity}
            roughness={0.25}
            metalness={0.75}
          />
        </mesh>
        <mesh position={[0, 0.38, 0.49]}>
          <boxGeometry args={[0.75, 0.08, 0.02]} />
          <meshBasicMaterial color="#ffffff" />
        </mesh>
        <mesh position={[0, 0.05, 0.49]}>
          <boxGeometry args={[0.75, 0.08, 0.02]} />
          <meshBasicMaterial color={isChanged ? '#06b6d4' : '#c4b5fd'} />
        </mesh>
        <mesh position={[0, -0.28, 0.49]}>
          <boxGeometry args={[0.75, 0.08, 0.02]} />
          <meshBasicMaterial color="#ffffff" />
        </mesh>
      </group>
    );
  };

  const scale = isSelected ? 1.4 : hovered ? 1.18 : 1.0;

  return (
    <group
      ref={groupRef}
      position={position}
      scale={[scale, scale, scale]}
      onClick={(e) => {
        e.stopPropagation();
        onClick(node.id);
      }}
      onPointerOver={(e) => {
        e.stopPropagation();
        setHovered(true);
        document.body.style.cursor = 'pointer';
      }}
      onPointerOut={() => {
        setHovered(false);
        document.body.style.cursor = 'default';
      }}
    >
      {/* Crown Jewel Accent Rings */}
      {isCrown && (
        <group>
          <mesh ref={ringRef}>
            <torusGeometry args={[1.6, 0.055, 16, 40]} />
            <meshBasicMaterial color={isFailing ? '#ef4444' : '#fbbf24'} />
          </mesh>
          <mesh ref={ring2Ref}>
            <torusGeometry args={[1.9, 0.035, 16, 40]} />
            <meshBasicMaterial color={isFailing ? '#ef4444' : '#ffffff'} />
          </mesh>
          <pointLight
            color={isFailing ? '#ef4444' : '#fbbf24'}
            intensity={3.5}
            distance={9}
            decay={2}
          />
        </group>
      )}

      {/* Executing Blue Glowing Aura Sphere & Orbiting Rings */}
      {isExecuting && (
        <group>
          <mesh>
            <sphereGeometry args={[1.55, 18, 18]} />
            <meshBasicMaterial color="#3b82f6" transparent opacity={0.35} wireframe />
          </mesh>
          <mesh ref={ringRef}>
            <torusGeometry args={[1.65, 0.055, 16, 40]} />
            <meshBasicMaterial color="#60a5fa" />
          </mesh>
          <mesh ref={ring2Ref}>
            <torusGeometry args={[1.92, 0.035, 16, 40]} />
            <meshBasicMaterial color="#93c5fd" />
          </mesh>
          <pointLight
            color="#3b82f6"
            intensity={4.8}
            distance={12}
            decay={2}
          />
        </group>
      )}

      {/* Changed Node Accent Ring */}
      {isChanged && !isCrown && !isExecuting && (
        <mesh ref={ringRef}>
          <torusGeometry args={[1.4, 0.04, 12, 24]} />
          <meshBasicMaterial color="#06b6d4" />
        </mesh>
      )}

      {/* Core 3D Geometry */}
      {renderShape()}

      {/* Floating 3D Holographic Label HUD */}
      <Html position={[0, 1.4, 0]} center distanceFactor={18} className="pointer-events-none select-none">
        <div
          style={{
            padding: '4px 10px',
            borderRadius: '10px',
            fontFamily: 'monospace',
            fontSize: '11px',
            whiteSpace: 'nowrap',
            backdropFilter: 'blur(12px)',
            border: isExecuting
              ? '2px solid #60a5fa'
              : isCrown
              ? '1.5px solid #fbbf24'
              : isFailing
              ? '1.5px solid #ef4444'
              : isChanged
              ? '1.5px solid #06b6d4'
              : isSelected
              ? '2px solid #a855f7'
              : '1px solid rgba(139, 92, 246, 0.35)',
            backgroundColor: isExecuting
              ? 'rgba(15, 23, 42, 0.95)'
              : isCrown
              ? 'rgba(69, 26, 3, 0.92)'
              : isFailing
              ? 'rgba(69, 10, 10, 0.92)'
              : isChanged
              ? 'rgba(8, 47, 73, 0.92)'
              : isSelected
              ? 'rgba(30, 15, 60, 0.95)'
              : 'rgba(14, 9, 29, 0.88)',
            color: isExecuting
              ? '#93c5fd'
              : isCrown
              ? '#fde68a'
              : isFailing
              ? '#fca5a5'
              : isChanged
              ? '#7dd3fc'
              : isSelected
              ? '#e9d5ff'
              : '#c4b5fd',
            boxShadow: isExecuting
              ? '0 0 25px rgba(59, 130, 246, 0.95), 0 0 50px rgba(37, 99, 235, 0.6)'
              : isCrown
              ? '0 0 20px rgba(251, 191, 36, 0.6)'
              : isFailing
              ? '0 0 20px rgba(239, 68, 68, 0.65)'
              : isChanged
              ? '0 0 16px rgba(6, 182, 212, 0.5)'
              : isSelected
              ? '0 0 18px rgba(168, 85, 247, 0.6)'
              : '0 4px 12px rgba(0,0,0,0.4)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 'bold' }}>
            {isExecuting ? (
              <span className="flex items-center gap-1 text-cyan-300">
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping inline-block" />
                <Zap style={{ width: 12, height: 12, color: '#60a5fa' }} />
              </span>
            ) : isCrown ? (
              <Crown style={{ width: 12, height: 12, color: '#fbbf24' }} />
            ) : isFailing ? (
              <ShieldAlert style={{ width: 12, height: 12, color: '#f87171' }} />
            ) : isChanged ? (
              <Zap style={{ width: 12, height: 12, color: '#38bdf8' }} />
            ) : (
              <ShieldCheck style={{ width: 12, height: 12, color: '#a855f7' }} />
            )}
            <span>{node.label || node.id.split('/').pop()}</span>
          </div>
          <div style={{ fontSize: '9px', opacity: 0.85, marginTop: '2px', display: 'flex', gap: '6px', justifyContent: 'center' }}>
            <span>{isExecuting ? 'RUNNING' : node.kind.toUpperCase()}</span>
            {node.loc > 0 && (
              <>
                <span>•</span>
                <span>{node.loc} LOC</span>
              </>
            )}
          </div>
        </div>
      </Html>
    </group>
  );
};

/* -------------------------------------------------------------------------- */
/*                                3D EDGE OBJECT                              */
/* -------------------------------------------------------------------------- */
interface Edge3DProps {
  edge: CEdge;
  start: [number, number, number];
  end: [number, number, number];
  isSelected: boolean;
  isFlowActive: boolean;
  onClick: (id: string) => void;
}

const CyberEdgeObject: React.FC<Edge3DProps> = ({
  edge,
  start,
  end,
  isSelected,
  isFlowActive,
  onClick,
}) => {
  const photonRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);

  const curve = useMemo(() => {
    const p1 = new THREE.Vector3(...start);
    const p2 = new THREE.Vector3(...end);
    const mid = new THREE.Vector3()
      .addVectors(p1, p2)
      .multiplyScalar(0.5);

    const dist = p1.distanceTo(p2);
    mid.y += Math.min(2.8, dist * 0.22);

    return new THREE.QuadraticBezierCurve3(p1, mid, p2);
  }, [start, end]);

  useFrame((state) => {
    if (!photonRef.current) return;
    const t = state.clock.getElapsedTime();
    const speed = isFlowActive ? 2.2 : 0.9;
    const progress = (t * speed) % 1;
    const point = curve.getPoint(progress);
    photonRef.current.position.copy(point);
  });

  const tubeRadius = isSelected ? 0.08 : isFlowActive ? 0.065 : hovered ? 0.07 : 0.038;
  const edgeColor = isSelected ? '#a855f7' : isFlowActive ? '#38bdf8' : hovered ? '#c084fc' : '#7c3aed';

  const tubeGeometry = useMemo(() => {
    return new THREE.TubeGeometry(curve, 28, tubeRadius, 8, false);
  }, [curve, tubeRadius]);

  const hitboxGeometry = useMemo(() => {
    return new THREE.TubeGeometry(curve, 16, 0.45, 6, false);
  }, [curve]);

  return (
    <group>
      {/* Invisible Expanded Click Hitbox */}
      <mesh
        geometry={hitboxGeometry}
        onClick={(e) => {
          e.stopPropagation();
          onClick(edge.id);
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHovered(true);
          document.body.style.cursor = 'pointer';
        }}
        onPointerOut={() => {
          setHovered(false);
          document.body.style.cursor = 'default';
        }}
      >
        <meshBasicMaterial transparent opacity={0} depthWrite={false} />
      </mesh>

      {/* Visible Glowing Conduit Tube */}
      <mesh geometry={tubeGeometry}>
        <meshBasicMaterial
          color={edgeColor}
          transparent
          opacity={isSelected ? 0.95 : isFlowActive ? 0.9 : hovered ? 0.85 : 0.45}
        />
      </mesh>

      {/* Flowing Data Particle */}
      <mesh ref={photonRef}>
        <sphereGeometry args={[isFlowActive ? 0.26 : 0.18, 14, 14]} />
        <meshBasicMaterial color={isFlowActive ? '#38bdf8' : '#e9d5ff'} />
        <pointLight
          color={isFlowActive ? '#38bdf8' : '#a855f7'}
          intensity={isFlowActive ? 4.5 : 2.5}
          distance={isFlowActive ? 5 : 3}
        />
      </mesh>
    </group>
  );
};

/* -------------------------------------------------------------------------- */
/*                                MAIN 3D WORLD                               */
/* -------------------------------------------------------------------------- */
export const CyberWorld3D: React.FC = () => {
  const {
    graph,
    mode,
    setMode,
    connected,
    selectedNodeId,
    selectedEdgeId,
    selectNode,
    selectEdge,
    setViewMode,
    setIsNodeStudioOpen,
    isProgramRunning,
    executingNodeIds,
    activeFlowEdgeIds,
  } = useReleaseStore();

  const [cameraPreset, setCameraPreset] = useState<CameraPreset | null>(null);
  const [dragMode, setDragMode] = useState<'orbit' | 'pan'>('orbit');
  const [navigationAction, setNavigationAction] = useState<NavigationAction | null>(null);

  const execSet = useMemo(() => new Set<string>(executingNodeIds || []), [executingNodeIds]);
  const flowEdgeSet = useMemo(() => new Set<string>(activeFlowEdgeIds || []), [activeFlowEdgeIds]);

  const triggerNav = (type: NavigationAction['type']) => {
    setNavigationAction({ type, ts: Date.now() });
  };

  // Calculate 3D coordinates for each node
  const nodePositions = useMemo(() => {
    const map = new Map<string, [number, number, number]>();

    graph.nodes.forEach((n, idx) => {
      const rawX = n.pos?.x ?? 120 + (idx % 5) * 210;
      const rawY = n.pos?.y ?? 100 + Math.floor(idx / 5) * 150;

      const x = (rawX - 550) * 0.046;
      const y = -(rawY - 320) * 0.042;

      let z = 0;
      if (n.is_crown_jewel) z = 4.5;
      else if (n.kind === 'infra') z = 3.6;
      else if (n.kind === 'service') z = 2.4;
      else if (n.kind === 'route') z = 0.5;
      else if (n.kind === 'sandbox') z = 1.8;
      else if (n.status === 'changed') z = -2.5;

      map.set(n.id, [x, y, z]);
    });

    return map;
  }, [graph.nodes]);

  const selectedPos = selectedNodeId ? nodePositions.get(selectedNodeId) ?? null : null;

  // System Architecture Metrics
  const totalNodes = graph.nodes.length;
  const totalEdges = graph.edges.length;
  const serviceCount = graph.nodes.filter(
    (n) => n.kind === 'service' || n.kind === 'route' || n.kind === 'sandbox'
  ).length;
  const moduleCount = graph.nodes.filter(
    (n) => n.kind === 'module' || n.kind === 'view'
  ).length;
  const infraCount = graph.nodes.filter(
    (n) => n.kind === 'infra' || n.is_crown_jewel
  ).length;

  const selectedNode = selectedNodeId
    ? graph.nodes.find((n) => n.id === selectedNodeId) ?? null
    : null;

  const incomingEdgesCount = selectedNode
    ? graph.edges.filter((e) => e.target === selectedNode.id).length
    : 0;
  const outgoingEdgesCount = selectedNode
    ? graph.edges.filter((e) => e.source === selectedNode.id).length
    : 0;

  return (
    <main className="command-shell select-none">
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />

      {/* Left Navigation Rail */}
      <aside className="side-rail">
        <div className="brand-mark">
          <Shield size={20} strokeWidth={2.4} />
          <span>RD</span>
        </div>
        <div className="rail-divider" />
        <button
          className="rail-action active"
          title="3D Architecture Space (Hotkey: V)"
          onClick={() => setViewMode('3d')}
        >
          <Boxes size={18} />
        </button>
        <button
          className="rail-action"
          title="2D Schematic Graph (Hotkey: V)"
          onClick={() => setViewMode('2d')}
        >
          <GitBranch size={18} />
        </button>
        <button className="rail-action" title="Telemetry"><Activity size={18} /></button>
        <button className="rail-action" title="Topology Explorer"><Gauge size={18} /></button>
        <div className="rail-spacer" />
        <button
          className={`rail-action ${mode === 'whatif' ? 'active text-amber-300' : ''}`}
          title="Toggle Simulation Mode (Hotkey: W)"
          onClick={() => setMode(mode === 'live' ? 'whatif' : 'live')}
        >
          <Crosshair size={18} />
        </button>
        <div className="rail-avatar">RD</div>
      </aside>

      {/* Main Workspace Area */}
      <section className="workspace">
        {/* Top Header Bar */}
        <header className="topbar">
          <div className="topbar-project">
            <div className="project-glyph"><AudioWaveform size={18} /></div>
            <div>
              <div className="eyebrow">SYSTEM ARCHITECTURE // REPOSITORY SCANNER</div>
              <div className="project-name">
                RELEASE <span>DOMINO</span>
                <span className="project-env">{mode.toUpperCase()}</span>
              </div>
            </div>
          </div>
          <div className="topbar-center">
            <span className="breadcrumb-muted">System</span>
            <span className="crumb-slash">/</span>
            <strong>Architecture Topology</strong>
            <span className="live-chip">
              <i /> 3D IMMERSIVE
            </span>
          </div>
          <div className="topbar-right">
            <button
              onClick={() => setViewMode('2d')}
              className="icon-button"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '4px 12px',
                width: 'auto',
                background: 'rgba(139, 92, 246, 0.2)',
                border: '1px solid #8b5cf6',
                color: '#c084fc',
                borderRadius: '9px',
                fontSize: '11px',
                fontWeight: 'bold',
                cursor: 'pointer',
              }}
              title="Toggle 2D Schematic Canvas (Hotkey: V)"
            >
              <Eye size={13} />
              <span>SWITCH TO 2D</span>
            </button>
            <div className={`connection-pill ${connected ? 'online' : 'offline'}`}>
              {connected ? <Wifi size={13} /> : <WifiOff size={13} />}
              <span>{connected ? 'TELEMETRY LIVE' : 'DEMO MODE'}</span>
            </div>
            <div className="topbar-divider" />
            <button className="icon-button" title="Command shortcuts"><Command size={15} /></button>
            <div className="user-chip">RD</div>
          </div>
        </header>

        {/* Page Heading & Status */}
        <div className="page-heading">
          <div>
            <div className="heading-eyebrow">
              <Sparkles size={12} />
              <span>CODE REPOSITORY DEPENDENCY GRAPH</span>
            </div>
            <h1>
              Architecture <em>Topology Explorer</em>
            </h1>
            <p>Interactive 3D dependency visualization. Inspect services, trace call graphs, and navigate architecture layers.</p>
          </div>
          <div className="heading-meta">
            <div className="meta-label">SYSTEM STATUS</div>
            <div className="risk-status guarded">
              <span className="risk-pulse" />
              OPERATIONAL
            </div>
            <div className="meta-foot">
              Interactive 3D graph • Real-time telemetry
            </div>
          </div>
        </div>

        {/* Metric Telemetry Strip */}
        <div className="metric-strip">
          <div className="metric-card">
            <div className="metric-icon violet"><Boxes size={16} /></div>
            <div className="metric-copy">
              <span>TOTAL MODULES</span>
              <strong>{totalNodes}<small> NODES</small></strong>
            </div>
            <div className="metric-trend">COMPONENTS</div>
          </div>
          <div className="metric-card">
            <div className="metric-icon mint"><Server size={16} /></div>
            <div className="metric-copy">
              <span>ENTRY SERVICES</span>
              <strong className="metric-word" style={{ color: '#34d399' }}>
                {serviceCount} <small>SERVICES</small>
              </strong>
            </div>
            <div className="metric-trend">ROOTS</div>
          </div>
          <div className="metric-card">
            <div className="metric-icon amber"><Network size={16} /></div>
            <div className="metric-copy">
              <span>DEPENDENCIES</span>
              <strong>{totalEdges}<small> CONDUITS</small></strong>
            </div>
            <div className="metric-trend">EDGES</div>
          </div>
          <div className="metric-card">
            <div className="metric-icon red"><Database size={16} /></div>
            <div className="metric-copy">
              <span>INFRASTRUCTURE</span>
              <strong>{infraCount.toString().padStart(2, '0')}<small> UNITS</small></strong>
            </div>
            <div className="metric-trend">PERSISTENCE</div>
          </div>
        </div>

        {/* Center Graph Section */}
        <section className="graph-section">
          {/* Top Line Header with 3D/2D Mode */}
          <div className="graph-topline">
            <div className="graph-title">
              <span className="graph-live-dot" />
              <div>
                <strong>Architecture Dependency Topology (3D)</strong>
                <small>Connected graph • {graph.edges.length} dependency conduits</small>
              </div>
            </div>
            <div className="graph-legend">
              <span><i className="legend-dot compromised" style={{ background: '#38bdf8' }} /> Routes & Services</span>
              <span><i className="legend-dot secure" style={{ background: '#a855f7' }} /> Modules & Logic</span>
              <span><i className="legend-dot crown" style={{ background: '#fbbf24' }} /> Databases & Infra</span>
            </div>
            <div className="graph-tools">
              <button
                onClick={() => setViewMode('2d')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px',
                  padding: '3px 9px',
                  borderRadius: '7px',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: '1px solid #8b5cf6',
                  background: 'rgba(139, 92, 246, 0.2)',
                  color: '#c084fc',
                }}
              >
                <Boxes size={12} />
                <span>3D VIEW</span>
              </button>
              <span className="zoom-hint">
                ARROWS / W-S: MOVE UP-DOWN • A-D: LEFT-RIGHT • DRAG: PAN/ORBIT
              </span>
              <span className="graph-mode">
                <Radio size={11} /> LIVE
              </span>
            </div>
          </div>

          {/* Integrated Architecture Navigation & Camera Control Bar */}
          <div className="flex items-center justify-between px-4 py-2 bg-[#0e091d]/95 border-b border-[#2d1b54] backdrop-blur-xl text-xs font-sans">
            {/* Left: Drag Mode & Movement Controls */}
            <div className="flex items-center gap-2">
              {/* Drag Mode Switcher */}
              <div className="flex items-center rounded-xl bg-[#06030c] border border-[#2d1b54] p-0.5">
                <button
                  onClick={() => setDragMode('orbit')}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition cursor-pointer ${
                    dragMode === 'orbit'
                      ? 'bg-[#8b5cf6] text-white shadow-[0_0_10px_#8b5cf6]'
                      : 'text-slate-400 hover:text-white'
                  }`}
                  title="Rotate view around target (Left-click drag)"
                >
                  <Compass className="w-3.5 h-3.5" />
                  <span>Orbit</span>
                </button>
                <button
                  onClick={() => setDragMode('pan')}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition cursor-pointer ${
                    dragMode === 'pan'
                      ? 'bg-[#8b5cf6] text-white shadow-[0_0_10px_#8b5cf6]'
                      : 'text-slate-400 hover:text-white'
                  }`}
                  title="Move camera position vertically/horizontally (Left-click drag)"
                >
                  <Move className="w-3.5 h-3.5" />
                  <span>Pan / Move</span>
                </button>
              </div>

              {/* Vertical & Directional Shift Controls */}
              <div className="flex items-center gap-1 ml-1">
                <button
                  onClick={() => triggerNav('up')}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#1b1035] hover:bg-[#28164f] border border-[#8b5cf6]/40 text-slate-200 hover:text-white transition font-mono font-bold cursor-pointer"
                  title="Move Camera Up (Hotkey: ArrowUp / W)"
                >
                  <ChevronUp className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Up</span>
                </button>
                <button
                  onClick={() => triggerNav('down')}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#1b1035] hover:bg-[#28164f] border border-[#8b5cf6]/40 text-slate-200 hover:text-white transition font-mono font-bold cursor-pointer"
                  title="Move Camera Down (Hotkey: ArrowDown / S)"
                >
                  <ChevronDown className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Down</span>
                </button>
                <button
                  onClick={() => triggerNav('left')}
                  className="flex items-center gap-1 px-2 py-1 rounded-lg bg-[#1b1035] hover:bg-[#28164f] border border-[#8b5cf6]/30 text-slate-300 hover:text-white transition font-mono cursor-pointer"
                  title="Move Left (Hotkey: ArrowLeft / A)"
                >
                  <ChevronLeft className="w-3.5 h-3.5 text-purple-400" />
                  <span>Left</span>
                </button>
                <button
                  onClick={() => triggerNav('right')}
                  className="flex items-center gap-1 px-2 py-1 rounded-lg bg-[#1b1035] hover:bg-[#28164f] border border-[#8b5cf6]/30 text-slate-300 hover:text-white transition font-mono cursor-pointer"
                  title="Move Right (Hotkey: ArrowRight / D)"
                >
                  <ChevronRight className="w-3.5 h-3.5 text-purple-400" />
                  <span>Right</span>
                </button>
              </div>

              {/* Zoom & Reset Controls */}
              <div className="flex items-center gap-1 ml-1 border-l border-[#2d1b54] pl-2">
                <button
                  onClick={() => triggerNav('zoomIn')}
                  className="p-1.5 rounded-lg bg-[#1b1035] hover:bg-[#28164f] border border-[#8b5cf6]/30 text-slate-300 hover:text-white transition cursor-pointer"
                  title="Zoom In (+)"
                >
                  <ZoomIn className="w-3.5 h-3.5 text-emerald-400" />
                </button>
                <button
                  onClick={() => triggerNav('zoomOut')}
                  className="p-1.5 rounded-lg bg-[#1b1035] hover:bg-[#28164f] border border-[#8b5cf6]/30 text-slate-300 hover:text-white transition cursor-pointer"
                  title="Zoom Out (-)"
                >
                  <ZoomOut className="w-3.5 h-3.5 text-emerald-400" />
                </button>
                <button
                  onClick={() => triggerNav('reset')}
                  className="flex items-center gap-1 px-2 py-1 rounded-lg bg-[#1b1035] hover:bg-[#28164f] border border-[#8b5cf6]/30 text-slate-300 hover:text-white transition text-[11px] cursor-pointer"
                  title="Reset Camera to Center"
                >
                  <RotateCcw className="w-3 h-3 text-slate-400" />
                  <span>Reset</span>
                </button>
              </div>
            </div>

            {/* Center Status Chip */}
            <div className="flex items-center gap-2">
              <span
                className={`px-3 py-1 rounded-full text-[10px] font-mono font-bold tracking-wider uppercase border flex items-center gap-1.5 transition ${
                  isProgramRunning
                    ? 'bg-blue-950/80 border-blue-400 text-blue-200 animate-pulse shadow-[0_0_15px_rgba(59,130,246,0.6)]'
                    : 'bg-[#1b1035] border-[#8b5cf6]/40 text-[#c084fc]'
                }`}
              >
                {isProgramRunning && (
                  <span className="w-2 h-2 rounded-full bg-blue-400 animate-ping inline-block" />
                )}
                {isProgramRunning ? 'PROJECT RUNNING LIVE • FLOW ACTIVE' : '3D ARCHITECTURE TOPOLOGY • INTERACTIVE'}
              </span>
            </div>

            {/* Right: Camera Presets */}
            <div className="flex items-center gap-1 text-xs font-mono">
              <span className="px-1 text-[10px] text-slate-400 flex items-center gap-1 font-sans">
                <Layers className="w-3.5 h-3.5 text-[#a855f7]" /> VIEWS:
              </span>
              <button
                onClick={() => setCameraPreset('overview')}
                className="px-2 py-1 rounded-lg text-slate-300 hover:text-white hover:bg-[#1b1035] transition cursor-pointer"
                title="Default Perspective Overview"
              >
                OVERVIEW
              </button>
              <button
                onClick={() => setCameraPreset('topdown')}
                className="px-2 py-1 rounded-lg text-emerald-300 hover:text-emerald-200 hover:bg-[#1b1035] transition flex items-center gap-1 cursor-pointer"
                title="Top-Down Plan View"
              >
                <Eye className="w-3 h-3 text-emerald-400" /> TOP-DOWN
              </button>
              <button
                onClick={() => setCameraPreset('services')}
                className="px-2 py-1 rounded-lg text-purple-300 hover:text-purple-200 hover:bg-[#1b1035] transition flex items-center gap-1 cursor-pointer"
                title="Focus on Core Services"
              >
                <Server className="w-3 h-3 text-purple-400" /> SERVICES
              </button>
              <button
                onClick={() => setCameraPreset('entrypoints')}
                className="px-2 py-1 rounded-lg text-sky-300 hover:text-sky-200 hover:bg-[#1b1035] transition flex items-center gap-1 cursor-pointer"
                title="Focus on Ingress & Routes"
              >
                <Radio className="w-3 h-3 text-sky-400" /> INGRESS
              </button>
              <button
                onClick={() => setCameraPreset('database')}
                className="px-2 py-1 rounded-lg text-amber-300 hover:text-amber-200 hover:bg-[#1b1035] transition flex items-center gap-1 cursor-pointer"
                title="Focus on Data & Storage Layer"
              >
                <Database className="w-3 h-3 text-amber-400" /> DATA
              </button>
            </div>
          </div>

          {/* 3D Viewport Stage */}
          <div
            className="graph-stage relative flex-1 min-h-0 bg-[#06030c] overflow-hidden"
            onContextMenu={(e) => e.preventDefault()}
          >
            <div className="graph-vignette" />
            <div className="graph-watermark">RELEASE DOMINO // 3D SYSTEM ARCHITECTURE</div>

            {/* Canvas with OrbitControls */}
            <Canvas
              camera={{ position: [0, 16, 28], fov: 45 }}
              gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
              onPointerMissed={() => {
                selectNode(null);
                selectEdge(null);
              }}
            >
              <color attach="background" args={['#0a0614']} />
              <fog attach="fog" args={['#0a0614', 24, 75]} />

              {/* Lighting */}
              <ambientLight color="#1e1035" intensity={1.6} />
              <directionalLight position={[15, 25, 20]} color="#c4b5fd" intensity={1.9} />
              <pointLight position={[-15, 10, -10]} color="#8b5cf6" intensity={1.8} distance={45} />
              <pointLight position={[15, 10, 10]} color="#06b6d4" intensity={1.3} distance={38} />
              <pointLight position={[0, -5, 0]} color="#10b981" intensity={0.8} distance={30} />

              {/* Starfield */}
              <Stars radius={65} depth={45} count={2800} factor={4} saturation={0.6} fade speed={0.7} />

              {/* Floor Grid */}
              <Grid
                position={[0, -7.5, 0]}
                args={[85, 85]}
                cellSize={1.5}
                cellThickness={1}
                cellColor="#2d1b54"
                sectionSize={6}
                sectionThickness={1.5}
                sectionColor="#8b5cf6"
                fadeDistance={55}
                fadeStrength={1.5}
              />

              {/* 3D Network Edges */}
              {graph.edges.map((edge) => {
                const sPos = nodePositions.get(edge.source);
                const tPos = nodePositions.get(edge.target);
                if (!sPos || !tPos) return null;

                const isFlowActive =
                  flowEdgeSet.has(edge.id) ||
                  execSet.has(edge.source) ||
                  execSet.has(edge.target) ||
                  isProgramRunning;

                return (
                  <CyberEdgeObject
                    key={edge.id}
                    edge={edge}
                    start={sPos}
                    end={tPos}
                    isSelected={edge.id === selectedEdgeId}
                    isFlowActive={isFlowActive}
                    onClick={(id) => selectEdge(id === selectedEdgeId ? null : id)}
                  />
                );
              })}

              {/* 3D Nodes */}
              {graph.nodes.map((node) => {
                const pos = nodePositions.get(node.id) || [0, 0, 0];
                const isExecuting =
                  execSet.has(node.id) ||
                  (isProgramRunning &&
                    execSet.size === 0 &&
                    (node.kind === 'service' || node.status === 'changed' || node.id.includes('main') || node.id.includes('server')));

                return (
                  <CyberNodeObject
                    key={node.id}
                    node={node}
                    position={pos}
                    isSelected={node.id === selectedNodeId}
                    isExecuting={isExecuting}
                    onClick={(id) => {
                      selectNode(id);
                      setIsNodeStudioOpen(true);
                    }}
                  />
                );
              })}

              {/* Smooth Camera & Navigation Controls */}
              <CameraController
                preset={cameraPreset}
                selectedPos={selectedPos}
                onPresetDone={() => setCameraPreset(null)}
                dragMode={dragMode}
                navigationAction={navigationAction}
              />
            </Canvas>

            {/* Floating Navigation D-Pad HUD (Bottom-Right) */}
            <div className="absolute bottom-5 right-5 z-20 flex flex-col items-center gap-1.5 p-2 rounded-2xl bg-[#0e091d]/90 border border-[#8b5cf6]/40 backdrop-blur-xl shadow-[0_15px_45px_rgba(10,5,25,0.8)] pointer-events-auto">
              <span className="text-[9px] font-mono text-slate-400 font-semibold tracking-wider">NAVIGATE</span>
              <button
                onClick={() => triggerNav('up')}
                className="w-8 h-8 rounded-lg bg-[#1b1035] hover:bg-[#28164f] border border-[#8b5cf6]/40 flex items-center justify-center text-cyan-400 hover:text-white transition cursor-pointer"
                title="Move Up (ArrowUp / W)"
              >
                <ChevronUp size={16} />
              </button>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => triggerNav('left')}
                  className="w-8 h-8 rounded-lg bg-[#1b1035] hover:bg-[#28164f] border border-[#8b5cf6]/40 flex items-center justify-center text-purple-400 hover:text-white transition cursor-pointer"
                  title="Move Left (ArrowLeft / A)"
                >
                  <ChevronLeft size={16} />
                </button>
                <button
                  onClick={() => triggerNav('reset')}
                  className="w-8 h-8 rounded-lg bg-[#06030c] hover:bg-[#1b1035] border border-[#8b5cf6]/40 flex items-center justify-center text-slate-300 hover:text-white transition cursor-pointer"
                  title="Reset Center"
                >
                  <RotateCcw size={14} />
                </button>
                <button
                  onClick={() => triggerNav('right')}
                  className="w-8 h-8 rounded-lg bg-[#1b1035] hover:bg-[#28164f] border border-[#8b5cf6]/40 flex items-center justify-center text-purple-400 hover:text-white transition cursor-pointer"
                  title="Move Right (ArrowRight / D)"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
              <button
                onClick={() => triggerNav('down')}
                className="w-8 h-8 rounded-lg bg-[#1b1035] hover:bg-[#28164f] border border-[#8b5cf6]/40 flex items-center justify-center text-cyan-400 hover:text-white transition cursor-pointer"
                title="Move Down (ArrowDown / S)"
              >
                <ChevronDown size={16} />
              </button>
              <div className="w-full h-px bg-[#2d1b54] my-0.5" />
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => triggerNav('zoomIn')}
                  className="w-8 h-7 rounded-lg bg-[#1b1035] hover:bg-[#28164f] border border-[#8b5cf6]/30 flex items-center justify-center text-emerald-400 hover:text-white transition text-xs font-bold cursor-pointer"
                  title="Zoom In (+)"
                >
                  +
                </button>
                <button
                  onClick={() => triggerNav('zoomOut')}
                  className="w-8 h-7 rounded-lg bg-[#1b1035] hover:bg-[#28164f] border border-[#8b5cf6]/30 flex items-center justify-center text-emerald-400 hover:text-white transition text-xs font-bold cursor-pointer"
                  title="Zoom Out (-)"
                >
                  -
                </button>
              </div>
            </div>

            {/* Floating Bottom-Left HUD: Module Inspector & Topology Overview */}
            <div className="absolute bottom-5 left-5 z-20 w-84 rounded-2xl bg-[#0e091d]/90 border border-[#8b5cf6]/40 p-3.5 backdrop-blur-xl shadow-[0_15px_45px_rgba(10,5,25,0.8)] font-sans pointer-events-auto">
              {selectedNode ? (
                <div>
                  <div className="flex items-center justify-between pb-2 border-b border-[#2d1b54]">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-slate-100 font-mono">
                      <FileCode className="w-4 h-4 text-cyan-400" />
                      <span>{selectedNode.label || selectedNode.id}</span>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#1b1035] text-purple-300 border border-[#8b5cf6]/30">
                      {selectedNode.kind.toUpperCase()}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 my-2.5">
                    <div className="rounded-xl bg-[#06030c] border border-[#2d1b54] p-2 text-center">
                      <div className="text-[10px] text-slate-400">INBOUND CONDUITS</div>
                      <div className="text-sm font-bold font-mono text-cyan-300 mt-0.5">
                        {incomingEdgesCount}
                      </div>
                    </div>
                    <div className="rounded-xl bg-[#06030c] border border-[#2d1b54] p-2 text-center">
                      <div className="text-[10px] text-slate-400">OUTBOUND CONDUITS</div>
                      <div className="text-sm font-bold font-mono text-purple-300 mt-0.5">
                        {outgoingEdgesCount}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 mt-2">
                    <button
                      onClick={() => setIsNodeStudioOpen(true)}
                      className="flex-1 py-1.5 px-3 rounded-xl bg-[#8b5cf6] hover:bg-[#7c3aed] text-white text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer shadow-[0_0_12px_rgba(139,92,246,0.4)]"
                    >
                      <Eye size={13} />
                      <span>Inspect in Node Studio</span>
                    </button>
                    <button
                      onClick={() => selectNode(null)}
                      className="py-1.5 px-2.5 rounded-xl bg-[#1b1035] hover:bg-[#28164f] border border-[#8b5cf6]/30 text-slate-300 hover:text-white text-xs transition cursor-pointer"
                    >
                      Clear
                    </button>
                  </div>
                </div>
              ) : (
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-200 mb-2">
                    <Layers className="w-3.5 h-3.5 text-[#a855f7]" /> Architecture Topology Breakdown
                  </div>
                  <div className="grid grid-cols-3 gap-1.5 mb-2.5">
                    <div className="rounded-xl bg-[#06030c] border border-[#2d1b54] p-2 text-center">
                      <div className="text-[9px] text-slate-400">SERVICES</div>
                      <div className="text-sm font-bold font-mono text-emerald-300 mt-0.5">{serviceCount}</div>
                    </div>
                    <div className="rounded-xl bg-[#06030c] border border-[#2d1b54] p-2 text-center">
                      <div className="text-[9px] text-slate-400">MODULES</div>
                      <div className="text-sm font-bold font-mono text-purple-300 mt-0.5">{moduleCount}</div>
                    </div>
                    <div className="rounded-xl bg-[#06030c] border border-[#2d1b54] p-2 text-center">
                      <div className="text-[9px] text-slate-400">DATABASES</div>
                      <div className="text-sm font-bold font-mono text-amber-300 mt-0.5">{infraCount}</div>
                    </div>
                  </div>
                  <div className="text-[11px] text-slate-400 leading-tight">
                    Click any 3D node to inspect module parameters, or use <span className="text-cyan-300 font-mono">W / S</span> or <span className="text-cyan-300 font-mono">Arrows</span> to move camera vertically.
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Footer Bar */}
          <div className="graph-footer">
            <span>
              <span className="footer-pulse" />
              SYSTEM ARCHITECTURE ENGINE ACTIVE
            </span>
            <span>ARROWS / W-S: MOVE UP-DOWN • A-D: LEFT-RIGHT • DRAG: PAN/ORBIT • V: 2D/3D • T: TERMINAL</span>
            <span className="footer-right">
              <Boxes size={12} /> ARCHITECTURE SCAN ONLINE
            </span>
          </div>
        </section>
      </section>
    </main>
  );
};

export default CyberWorld3D;
