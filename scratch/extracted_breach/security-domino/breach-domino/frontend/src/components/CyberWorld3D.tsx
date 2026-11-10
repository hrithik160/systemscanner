import React, { useMemo, useRef, useState, useEffect } from 'react';
import * as THREE from 'three';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, Stars, Grid, Html } from '@react-three/drei';
import { type OrbitControls as OrbitControlsType } from 'three-stdlib';
import { useGraphStore } from '../store/graphStore';
import { GNode, GEdge } from '../../../shared/types';
import {
  Crown,
  ShieldAlert,
  ShieldCheck,
  Crosshair,
  Ban,
  Compass,
  Radio,
  Eye,
  Target,
} from 'lucide-react';

/* -------------------------------------------------------------------------- */
/*                                3D CAMERA CONTROLLER                         */
/* -------------------------------------------------------------------------- */
interface CameraControlProps {
  preset: 'overview' | 'crown' | 'ingress' | 'tactical' | null;
  selectedPos: [number, number, number] | null;
  onPresetDone: () => void;
}

const CameraController: React.FC<CameraControlProps> = ({
  preset,
  selectedPos,
  onPresetDone,
}) => {
  const { camera } = useThree();
  const controlsRef = useRef<OrbitControlsType>(null);

  useEffect(() => {
    if (!preset) return;

    if (preset === 'overview') {
      camera.position.set(0, 16, 28);
      camera.lookAt(0, 0, 0);
      controlsRef.current?.target.set(0, 0, 0);
    } else if (preset === 'crown') {
      camera.position.set(14, 8, 14);
      camera.lookAt(18, -1, 4);
      controlsRef.current?.target.set(18, -1, 4);
    } else if (preset === 'ingress') {
      camera.position.set(-16, 8, 14);
      camera.lookAt(-18, -1, -2);
      controlsRef.current?.target.set(-18, -1, -2);
    } else if (preset === 'tactical') {
      camera.position.set(0, 32, 2);
      camera.lookAt(0, 0, 0);
      controlsRef.current?.target.set(0, 0, 0);
    }

    onPresetDone();
  }, [preset, camera, onPresetDone]);

  useEffect(() => {
    if (selectedPos) {
      controlsRef.current?.target.set(...selectedPos);
    }
  }, [selectedPos]);

  return (
    <OrbitControls
      ref={controlsRef}
      enableDamping
      dampingFactor={0.06}
      minDistance={6}
      maxDistance={65}
      maxPolarAngle={Math.PI / 2 + 0.05}
    />
  );
};

/* -------------------------------------------------------------------------- */
/*                                3D NODE OBJECT                              */
/* -------------------------------------------------------------------------- */
interface Node3DProps {
  node: GNode;
  position: [number, number, number];
  isSelected: boolean;
  isCompromisedByAttack: boolean;
  isCurrentTarget: boolean;
  onClick: (id: string) => void;
}

const CyberNodeObject: React.FC<Node3DProps> = ({
  node,
  position,
  isSelected,
  isCompromisedByAttack,
  isCurrentTarget,
  onClick,
}) => {
  const groupRef = useRef<THREE.Group>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  const ring2Ref = useRef<THREE.Mesh>(null);
  const shieldRingRef = useRef<THREE.Mesh>(null);
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
    if (shieldRingRef.current) {
      shieldRingRef.current.rotation.z = t * 1.3;
    }
  });

  const isCrown = node.is_crown_jewel;
  const isDecoy = node.is_decoy;
  const isPatched = node.vulnerabilities.length === 0 && node.cvss_score <= 1.0 && !isCrown && !isDecoy;
  const isCompromised = isCompromisedByAttack || node.status === 'compromised';

  let mainColor = '#8b5cf6';
  let emissiveColor = '#8b5cf6';
  let emissiveIntensity = isSelected ? 1.6 : isCurrentTarget ? 1.4 : 0.45;

  if (isCrown) {
    mainColor = isCompromised ? '#ef4444' : '#fbbf24';
    emissiveColor = isCompromised ? '#ef4444' : '#f59e0b';
    emissiveIntensity = isCompromised ? 1.9 : 1.5;
  } else if (isDecoy) {
    mainColor = '#10b981';
    emissiveColor = '#10b981';
    emissiveIntensity = 1.4;
  } else if (isPatched) {
    mainColor = '#10b981';
    emissiveColor = '#10b981';
    emissiveIntensity = 1.2;
  } else if (isCompromised) {
    mainColor = '#ef4444';
    emissiveColor = '#ef4444';
    emissiveIntensity = 1.7;
  } else if (isCurrentTarget) {
    mainColor = '#f59e0b';
    emissiveColor = '#f59e0b';
    emissiveIntensity = 1.5;
  } else if (node.status === 'isolated') {
    mainColor = '#475569';
    emissiveColor = '#1e1b4b';
    emissiveIntensity = 0.15;
  }

  const renderShape = () => {
    switch (node.type) {
      case 'Database':
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
              <meshBasicMaterial color={isPatched ? '#10b981' : '#ffffff'} />
            </mesh>
            <mesh position={[0, -0.38, 0]}>
              <torusGeometry args={[0.75, 0.045, 12, 24]} />
              <meshBasicMaterial color={isPatched ? '#10b981' : '#ffffff'} />
            </mesh>
          </group>
        );

      case 'IAM':
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

      case 'Workstation':
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

      case 'IoT':
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
            <mesh position={[0.26, 0.88, 0.26]}>
              <sphereGeometry args={[0.08, 12, 12]} />
              <meshBasicMaterial color={emissiveColor} />
            </mesh>
          </group>
        );

      case 'Server':
      default:
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
            <mesh position={[0, 0.4, 0.49]}>
              <boxGeometry args={[0.75, 0.08, 0.02]} />
              <meshBasicMaterial color={isPatched ? '#10b981' : '#ffffff'} />
            </mesh>
            <mesh position={[0, 0.08, 0.49]}>
              <boxGeometry args={[0.75, 0.08, 0.02]} />
              <meshBasicMaterial color={isPatched ? '#10b981' : '#c4b5fd'} />
            </mesh>
            <mesh position={[0, -0.24, 0.49]}>
              <boxGeometry args={[0.75, 0.08, 0.02]} />
              <meshBasicMaterial color={isPatched ? '#10b981' : '#ffffff'} />
            </mesh>
          </group>
        );
    }
  };

  const scale = isSelected ? 1.38 : isCurrentTarget ? 1.25 : hovered ? 1.18 : 1.0;

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
      {/* Crown Jewel Multi-Orbital Halos */}
      {isCrown && (
        <group>
          <mesh ref={ringRef}>
            <torusGeometry args={[1.55, 0.055, 16, 40]} />
            <meshBasicMaterial color={isCompromised ? '#ef4444' : '#fbbf24'} />
          </mesh>
          <mesh ref={ring2Ref}>
            <torusGeometry args={[1.85, 0.035, 16, 40]} />
            <meshBasicMaterial color={isCompromised ? '#ef4444' : '#ffffff'} />
          </mesh>
          <pointLight
            color={isCompromised ? '#ef4444' : '#fbbf24'}
            intensity={3.5}
            distance={8}
            decay={2}
          />
        </group>
      )}

      {/* Decoy Honeypot Containment Rings */}
      {isDecoy && (
        <group>
          <mesh ref={ringRef}>
            <torusGeometry args={[1.4, 0.04, 16, 32]} />
            <meshBasicMaterial color="#10b981" />
          </mesh>
          <pointLight color="#10b981" intensity={2.5} distance={6} decay={2} />
        </group>
      )}

      {/* Patched Defense Shield Orbital */}
      {isPatched && (
        <mesh ref={shieldRingRef}>
          <torusGeometry args={[1.35, 0.04, 16, 32]} />
          <meshBasicMaterial color="#10b981" />
        </mesh>
      )}

      {/* Target Assault Lock Ring */}
      {isCurrentTarget && (
        <mesh>
          <torusGeometry args={[1.5, 0.03, 16, 24]} />
          <meshBasicMaterial color="#f59e0b" wireframe />
        </mesh>
      )}

      {/* Compromised Hazard Pulse Sphere */}
      {isCompromised && (
        <mesh>
          <sphereGeometry args={[1.65, 16, 16]} />
          <meshBasicMaterial color="#ef4444" transparent opacity={0.2} wireframe />
        </mesh>
      )}

      {/* Core 3D Geometry */}
      {renderShape()}

      {/* Floating 3D Holographic Label */}
      <Html position={[0, 1.35, 0]} center distanceFactor={18} className="pointer-events-none select-none">
        <div
          style={{
            padding: '4px 10px',
            borderRadius: '10px',
            fontFamily: 'monospace',
            fontSize: '11px',
            whiteSpace: 'nowrap',
            backdropFilter: 'blur(12px)',
            border: isCrown
              ? '1.5px solid #fbbf24'
              : isCompromised
              ? '1.5px solid #ef4444'
              : isCurrentTarget
              ? '1.5px solid #f59e0b'
              : isPatched
              ? '1.5px solid #10b981'
              : isSelected
              ? '2px solid #a855f7'
              : '1px solid rgba(139, 92, 246, 0.35)',
            backgroundColor: isCrown
              ? 'rgba(69, 26, 3, 0.9)'
              : isCompromised
              ? 'rgba(69, 10, 10, 0.9)'
              : isCurrentTarget
              ? 'rgba(69, 45, 10, 0.9)'
              : isPatched
              ? 'rgba(6, 78, 59, 0.9)'
              : isSelected
              ? 'rgba(30, 15, 60, 0.92)'
              : 'rgba(14, 9, 29, 0.88)',
            color: isCrown
              ? '#fde68a'
              : isCompromised
              ? '#fca5a5'
              : isCurrentTarget
              ? '#fef08a'
              : isPatched
              ? '#6ee7b7'
              : isSelected
              ? '#e9d5ff'
              : '#c4b5fd',
            boxShadow: isCrown
              ? '0 0 20px rgba(251, 191, 36, 0.6)'
              : isCompromised
              ? '0 0 20px rgba(239, 68, 68, 0.65)'
              : isPatched
              ? '0 0 16px rgba(16, 185, 129, 0.5)'
              : isSelected
              ? '0 0 18px rgba(168, 85, 247, 0.6)'
              : '0 4px 12px rgba(0,0,0,0.4)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 'bold' }}>
            {isCrown ? (
              <Crown style={{ width: 12, height: 12, color: '#fbbf24' }} />
            ) : isCompromised ? (
              <ShieldAlert style={{ width: 12, height: 12, color: '#f87171' }} />
            ) : isCurrentTarget ? (
              <Target style={{ width: 12, height: 12, color: '#f59e0b' }} />
            ) : isPatched ? (
              <ShieldCheck style={{ width: 12, height: 12, color: '#34d399' }} />
            ) : isDecoy ? (
              <Crosshair style={{ width: 12, height: 12, color: '#34d399' }} />
            ) : (
              <ShieldCheck style={{ width: 12, height: 12, color: '#a855f7' }} />
            )}
            <span>{node.label}</span>
          </div>
          <div style={{ fontSize: '9px', opacity: 0.85, marginTop: '2px', display: 'flex', gap: '6px', justifyContent: 'center' }}>
            <span>{node.type}</span>
            <span>•</span>
            <span>{isCompromised ? 'COMPROMISED' : isPatched ? 'PATCHED' : "CVSS " + node.cvss_score.toFixed(1)}</span>
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
  edge: GEdge;
  start: [number, number, number];
  end: [number, number, number];
  isSelected: boolean;
  isTraversed: boolean;
  isCurrentlyTraversing: boolean;
  onClick: (id: string) => void;
}

const CyberEdgeObject: React.FC<Edge3DProps> = ({
  edge,
  start,
  end,
  isSelected,
  isTraversed,
  isCurrentlyTraversing,
  onClick,
}) => {
  const photonRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);

  const curve = useMemo(() => {
    const p1 = new THREE.Vector3(...start);
    const p2 = new THREE.Vector3(...end);
    const mid = new THREE.Vector3().addVectors(p1, p2).multiplyScalar(0.5);
    const dist = p1.distanceTo(p2);
    mid.y += Math.min(2.8, dist * 0.13);
    return new THREE.QuadraticBezierCurve3(p1, mid, p2);
  }, [start, end]);

  const tubeRadius = isSelected
    ? 0.08
    : hovered
    ? 0.065
    : isCurrentlyTraversing
    ? 0.075
    : isTraversed
    ? 0.055
    : 0.035;

  const tubeGeometry = useMemo(() => {
    return new THREE.TubeGeometry(curve, 28, tubeRadius, 8, false);
  }, [curve, tubeRadius]);

  const hitboxGeometry = useMemo(() => {
    return new THREE.TubeGeometry(curve, 16, 0.5, 6, false);
  }, [curve]);

  const midPoint = useMemo(() => {
    return curve.getPoint(0.5);
  }, [curve]);

  // Traveling photon particle ONLY shoots along the currently traversing active edge
  useFrame((state) => {
    if (!isCurrentlyTraversing || !photonRef.current) return;
    const t = (state.clock.getElapsedTime() * 1.5) % 1;
    const pt = curve.getPoint(t);
    photonRef.current.position.copy(pt);
  });

  const isFirewalled = edge.status === 'firewalled';

  let edgeColor = '#8b5cf6';
  if (isFirewalled) edgeColor = '#ef4444';
  else if (isCurrentlyTraversing) edgeColor = '#f43f5e';
  else if (isTraversed) edgeColor = '#ef4444';
  else if (isSelected) edgeColor = '#a855f7';
  else if (hovered) edgeColor = '#c4b5fd';

  return (
    <group>
      {/* Invisible Collision Hitbox */}
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
          opacity={isFirewalled ? 0.35 : isCurrentlyTraversing ? 1.0 : isTraversed ? 0.9 : isSelected ? 0.9 : 0.45}
        />
      </mesh>

      {/* Firewalled Hazard Barrier Disc at Midpoint */}
      {isFirewalled && (
        <group position={midPoint}>
          <mesh>
            <cylinderGeometry args={[0.65, 0.65, 0.1, 16]} />
            <meshStandardMaterial color="#ef4444" emissive="#ef4444" emissiveIntensity={1.5} />
          </mesh>
          <mesh>
            <torusGeometry args={[0.78, 0.04, 12, 24]} />
            <meshBasicMaterial color="#ffffff" />
          </mesh>
          <Html center distanceFactor={16} className="pointer-events-none select-none">
            <div className="px-2 py-0.5 rounded bg-red-950/90 border border-red-500 text-red-200 font-mono text-[9px] font-bold shadow-lg flex items-center gap-1">
              <Ban className="w-3 h-3 text-red-400" /> BLOCKED
            </div>
          </Html>
        </group>
      )}

      {/* Attack Photon Particle - active only during traversal */}
      {isCurrentlyTraversing && !isFirewalled && (
        <mesh ref={photonRef}>
          <sphereGeometry args={[0.26, 14, 14]} />
          <meshBasicMaterial color="#ffffff" />
          <pointLight color="#f43f5e" intensity={4} distance={4} />
        </mesh>
      )}
    </group>
  );
};

/* -------------------------------------------------------------------------- */
/*                                MAIN 3D WORLD                               */
/* -------------------------------------------------------------------------- */
export const CyberWorld3D: React.FC = () => {
  const {
    mode,
    liveGraph,
    whatIfGraph,
    simPlayback,
    selectedNodeId,
    selectedEdgeId,
    selectNode,
    selectEdge,
    patchNode,
    firewallEdge,
    activeTool,
  } = useGraphStore();

  const [cameraPreset, setCameraPreset] = useState<'overview' | 'crown' | 'ingress' | 'tactical' | null>(null);

  const graph = mode === 'live' ? liveGraph : whatIfGraph;

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
      else if (n.is_decoy) z = 3.2;
      else if (n.type === 'IoT') z = -3.8;
      else if (n.type === 'Workstation') z = -1.6;
      else if (n.type === 'Server') z = 0.6;
      else if (n.type === 'IAM') z = 2.6;
      else if (n.type === 'Database') z = 3.6;

      map.set(n.id, [x, y, z]);
    });

    return map;
  }, [graph.nodes]);

  const selectedPos = selectedNodeId ? nodePositions.get(selectedNodeId) ?? null : null;

  const handleNodeClick = (nodeId: string) => {
    if (activeTool === 'patch') {
      patchNode(nodeId);
    } else {
      selectNode(nodeId === selectedNodeId ? null : nodeId);
    }
  };

  const handleEdgeClick = (edgeId: string) => {
    if (activeTool === 'scissors') {
      firewallEdge(edgeId);
    } else {
      selectEdge(edgeId === selectedEdgeId ? null : edgeId);
    }
  };

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', background: '#0a0614' }}>
      {/* 3D Camera Preset Overlay Bar */}
      <div className="absolute top-4 left-6 z-20 flex items-center gap-1.5 p-1 rounded-xl bg-[#0e091d]/90 border border-[#8b5cf6]/40 backdrop-blur-md shadow-xl text-xs font-mono">
        <span className="px-2 text-[10px] text-slate-400 font-sans flex items-center gap-1">
          <Compass className="w-3.5 h-3.5 text-[#a855f7]" /> CAMERA:
        </span>
        <button
          onClick={() => setCameraPreset('overview')}
          className="px-2.5 py-1 rounded-lg text-slate-300 hover:text-white hover:bg-[#1b1035] transition cursor-pointer"
        >
          OVERVIEW
        </button>
        <button
          onClick={() => setCameraPreset('crown')}
          className="px-2.5 py-1 rounded-lg text-amber-300 hover:text-amber-200 hover:bg-[#1b1035] transition flex items-center gap-1 cursor-pointer"
        >
          <Crown className="w-3 h-3 text-amber-400" /> CROWN
        </button>
        <button
          onClick={() => setCameraPreset('ingress')}
          className="px-2.5 py-1 rounded-lg text-sky-300 hover:text-sky-200 hover:bg-[#1b1035] transition flex items-center gap-1 cursor-pointer"
        >
          <Radio className="w-3 h-3 text-sky-400" /> INGRESS
        </button>
        <button
          onClick={() => setCameraPreset('tactical')}
          className="px-2.5 py-1 rounded-lg text-emerald-300 hover:text-emerald-200 hover:bg-[#1b1035] transition flex items-center gap-1 cursor-pointer"
        >
          <Eye className="w-3 h-3 text-emerald-400" /> TACTICAL
        </button>
      </div>

      <Canvas
        camera={{ position: [0, 15, 28], fov: 45 }}
        gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
        onPointerMissed={() => {
          selectNode(null);
          selectEdge(null);
        }}
      >
        <color attach="background" args={['#0a0614']} />
        <fog attach="fog" args={['#0a0614', 24, 68]} />

        {/* Lighting */}
        <ambientLight color="#1e1035" intensity={1.6} />
        <directionalLight position={[15, 25, 20]} color="#c4b5fd" intensity={1.9} />
        <pointLight position={[-15, 10, -10]} color="#8b5cf6" intensity={1.8} distance={45} />
        <pointLight position={[15, 10, 10]} color="#ef4444" intensity={1.3} distance={38} />
        <pointLight position={[0, -5, 0]} color="#10b981" intensity={0.8} distance={30} />

        {/* Starfield */}
        <Stars radius={65} depth={45} count={2800} factor={4} saturation={0.6} fade speed={0.7} />

        {/* Floor Grid */}
        <Grid
          position={[0, -7.5, 0]}
          args={[80, 80]}
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

          const isTraversed = simPlayback.revealedEdges.includes(edge.id);
          const isCurrentlyTraversing = edge.id === simPlayback.activeEdgeId;

          return (
            <CyberEdgeObject
              key={edge.id}
              edge={edge}
              start={sPos}
              end={tPos}
              isSelected={edge.id === selectedEdgeId}
              isTraversed={isTraversed}
              isCurrentlyTraversing={isCurrentlyTraversing}
              onClick={handleEdgeClick}
            />
          );
        })}

        {/* 3D Infrastructure Nodes */}
        {graph.nodes.map((node) => {
          const pos = nodePositions.get(node.id) || [0, 0, 0];
          const isCompromisedByAttack = simPlayback.revealedNodes.includes(node.id);
          const isCurrentTarget = node.id === simPlayback.targetNodeId;

          return (
            <CyberNodeObject
              key={node.id}
              node={node}
              position={pos}
              isSelected={node.id === selectedNodeId}
              isCompromisedByAttack={isCompromisedByAttack}
              isCurrentTarget={isCurrentTarget}
              onClick={handleNodeClick}
            />
          );
        })}

        {/* Smooth OrbitControls & Camera Navigation */}
        <CameraController
          preset={cameraPreset}
          selectedPos={selectedPos}
          onPresetDone={() => setCameraPreset(null)}
        />
      </Canvas>
    </div>
  );
};

export default CyberWorld3D;
