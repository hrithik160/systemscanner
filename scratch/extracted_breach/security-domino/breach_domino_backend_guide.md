# Breach Domino Simulator — Standalone Backend Build (Person A)

This guide lets you build, run, and verify **100% of Person A's backend** standalone—without waiting on Person B (`types.ts` / Zustand store) or Person C (`topology.sample.json` / React Flow UI). When your teammates are ready to integrate, your `/ws` endpoint and `/shared` files already match the frozen contract in Section 4 of the Team Guide PDF.

## 1. Standalone Folder Layout

```text
breach-domino/
├── shared/
│   ├── topology.sample.json     # 15 nodes, 30 edges, 1 crown jewel (ready now; swap with Person C later)
│   ├── sample_events.jsonl      # Task A2 - 8-step breach chain (Printer -> Dev Laptop -> IAM -> Prod DB)
│   └── manual_map.json          # Task A3 - Fallback asset alias lookup
└── backend/
    ├── .env.example             # Task A7 - SOURCE=replay|live environment config
    ├── run.sh                   # Task A7 - Single-command backend launcher
    ├── main.py                  # Task A1 & A7 - FastAPI (/ws, /health, /siem/ingest, + standalone /demo UI)
    ├── bus.py                   # Task A1 - Async pub/sub Event Bus
    ├── graph_state.py           # Task A1 - In-memory GraphState + apply_event()
    ├── resolver.py              # Task A3 - IP/hostname/cloud_id -> node_id resolver
    ├── test_backend.py          # Automated verification suite for Tasks A1–A6
    └── adapters/
        ├── __init__.py
        ├── replay.py            # Task A2 (DO FIRST) - JSONL replay with timing, speed, start/pause/reset
        ├── cloud.py             # Task A4 - Read-only boto3 poller (30-60s) + snapshot diffing
        ├── ws_source.py         # Task A5 - Upstream WebSocket subscriber with exponential backoff
        └── siem.py              # Task A6 - SIEM log parser + resolver integration
```

## 2. Shared Mock & Replay Files (`/shared`)

### `/shared/sample_events.jsonl` (Task A2 — DO FIRST)
```json
{"ts": 1730000001000, "type": "node_compromised", "id": "node-printer-01", "payload": {"status": "compromised"}, "source": "replay"}
{"ts": 1730000002500, "type": "edge_active_attack", "id": "edge-01", "payload": {"status": "active_attack"}, "source": "replay"}
{"ts": 1730000004000, "type": "node_compromised", "id": "node-dev-laptop", "payload": {"status": "compromised"}, "source": "replay"}
{"ts": 1730000005500, "type": "cve_found", "id": "node-dev-laptop", "payload": {"vulnerabilities": ["CVE-2024-3094", "CVE-2023-4863"], "cvss_score": 8.8}, "source": "replay"}
{"ts": 1730000007000, "type": "edge_active_attack", "id": "edge-10", "payload": {"status": "active_attack"}, "source": "replay"}
{"ts": 1730000008500, "type": "node_compromised", "id": "node-iam-admin", "payload": {"status": "compromised"}, "source": "replay"}
{"ts": 1730000010000, "type": "edge_active_attack", "id": "edge-29", "payload": {"status": "active_attack"}, "source": "replay"}
{"ts": 1730000011500, "type": "node_compromised", "id": "node-prod-db", "payload": {"status": "compromised"}, "source": "replay"}
```

### `/shared/manual_map.json` (Task A3 — Asset Resolver Fallback)
```json
{
  "10.0.1.50": "node-printer-01",
  "hp-laserjet-3rd-fl": "node-printer-01",
  "printer-3f": "node-printer-01",
  "10.0.2.14": "node-dev-laptop",
  "dev-mbp-alex": "node-dev-laptop",
  "alex-laptop": "node-dev-laptop",
  "10.0.10.12": "node-build-srv",
  "jenkins-runner-01": "node-build-srv",
  "arn:aws:iam::123456789012:role/AdminRole": "node-iam-admin",
  "iam-deploy-admin": "node-iam-admin",
  "10.0.99.10": "node-prod-db",
  "rds-prod-customers": "node-prod-db",
  "prod-postgres-primary": "node-prod-db"
}
```

### `/shared/topology.sample.json` (15 Nodes, 30 Edges, 1 Crown Jewel)
Lets you run and test your backend immediately before Person C pushes their topology file.
```json
{
  "nodes": [
    {
      "id": "node-printer-01",
      "label": "3rd Floor Office Printer",
      "type": "IoT",
      "cvss_score": 7.5,
      "vulnerabilities": [
        "CVE-2022-3942"
      ],
      "is_crown_jewel": false,
      "status": "secure",
      "refs": {
        "ip": "10.0.1.50",
        "hostname": "hp-laserjet-3rd-fl",
        "cloud_id": "iot-printer-01"
      },
      "pos": {
        "x": 80,
        "y": 120
      }
    },
    {
      "id": "node-badge-reader",
      "label": "Lobby Badge Reader",
      "type": "IoT",
      "cvss_score": 6.8,
      "vulnerabilities": [
        "CVE-2021-36260"
      ],
      "is_crown_jewel": false,
      "status": "secure",
      "refs": {
        "ip": "10.0.1.55",
        "hostname": "hid-lobby-01",
        "cloud_id": "iot-badge-01"
      },
      "pos": {
        "x": 80,
        "y": 280
      }
    },
    {
      "id": "node-hvac-ctrl",
      "label": "Smart HVAC Controller",
      "type": "IoT",
      "cvss_score": 5.4,
      "vulnerabilities": [
        "CVE-2020-25078"
      ],
      "is_crown_jewel": false,
      "status": "secure",
      "refs": {
        "ip": "10.0.1.60",
        "hostname": "bms-hvac-main",
        "cloud_id": "iot-hvac-01"
      },
      "pos": {
        "x": 80,
        "y": 440
      }
    },
    {
      "id": "node-dev-laptop",
      "label": "Intern Dev Laptop",
      "type": "Workstation",
      "cvss_score": 8.1,
      "vulnerabilities": [
        "CVE-2023-4863"
      ],
      "is_crown_jewel": false,
      "status": "secure",
      "refs": {
        "ip": "10.0.2.14",
        "hostname": "dev-mbp-alex",
        "cloud_id": "ws-dev-14"
      },
      "pos": {
        "x": 280,
        "y": 120
      }
    },
    {
      "id": "node-sre-workstation",
      "label": "SRE Admin Workstation",
      "type": "Workstation",
      "cvss_score": 6.2,
      "vulnerabilities": [
        "CVE-2023-38545"
      ],
      "is_crown_jewel": false,
      "status": "secure",
      "refs": {
        "ip": "10.0.2.20",
        "hostname": "sre-thinkpad-priya",
        "cloud_id": "ws-sre-20"
      },
      "pos": {
        "x": 280,
        "y": 280
      }
    },
    {
      "id": "node-finance-pc",
      "label": "Finance Analyst PC",
      "type": "Workstation",
      "cvss_score": 7.2,
      "vulnerabilities": [
        "CVE-2023-36884"
      ],
      "is_crown_jewel": false,
      "status": "secure",
      "refs": {
        "ip": "10.0.2.35",
        "hostname": "fin-win11-04",
        "cloud_id": "ws-fin-35"
      },
      "pos": {
        "x": 280,
        "y": 440
      }
    },
    {
      "id": "node-bastion",
      "label": "SSH Bastion Host",
      "type": "Server",
      "cvss_score": 5.9,
      "vulnerabilities": [
        "CVE-2024-6387"
      ],
      "is_crown_jewel": false,
      "status": "secure",
      "refs": {
        "ip": "10.0.10.5",
        "hostname": "bastion-us-east",
        "cloud_id": "i-0a1b2c3d4e5f00001"
      },
      "pos": {
        "x": 500,
        "y": 80
      }
    },
    {
      "id": "node-build-srv",
      "label": "CI/CD Build Runner",
      "type": "Server",
      "cvss_score": 8.6,
      "vulnerabilities": [
        "CVE-2024-23897"
      ],
      "is_crown_jewel": false,
      "status": "secure",
      "refs": {
        "ip": "10.0.10.12",
        "hostname": "jenkins-runner-01",
        "cloud_id": "i-0a1b2c3d4e5f00002"
      },
      "pos": {
        "x": 500,
        "y": 200
      }
    },
    {
      "id": "node-api-gw",
      "label": "Public API Gateway",
      "type": "Server",
      "cvss_score": 7.4,
      "vulnerabilities": [
        "CVE-2023-44487"
      ],
      "is_crown_jewel": false,
      "status": "secure",
      "refs": {
        "ip": "10.0.10.25",
        "hostname": "envoy-edge-gw",
        "cloud_id": "i-0a1b2c3d4e5f00003"
      },
      "pos": {
        "x": 500,
        "y": 320
      }
    },
    {
      "id": "node-file-share",
      "label": "Internal SMB File Server",
      "type": "Server",
      "cvss_score": 7.8,
      "vulnerabilities": [
        "CVE-2022-41128"
      ],
      "is_crown_jewel": false,
      "status": "secure",
      "refs": {
        "ip": "10.0.10.40",
        "hostname": "corp-nas-smb",
        "cloud_id": "i-0a1b2c3d4e5f00004"
      },
      "pos": {
        "x": 500,
        "y": 440
      }
    },
    {
      "id": "node-k8s-worker",
      "label": "K8s App Worker Node",
      "type": "Server",
      "cvss_score": 6.9,
      "vulnerabilities": [
        "CVE-2024-21626"
      ],
      "is_crown_jewel": false,
      "status": "secure",
      "refs": {
        "ip": "10.0.20.11",
        "hostname": "eks-worker-prod-01",
        "cloud_id": "i-0a1b2c3d4e5f00005"
      },
      "pos": {
        "x": 720,
        "y": 140
      }
    },
    {
      "id": "node-iam-admin",
      "label": "CI/CD Deploy IAM Role",
      "type": "IAM",
      "cvss_score": 8.5,
      "vulnerabilities": [],
      "is_crown_jewel": false,
      "status": "secure",
      "refs": {
        "ip": "169.254.169.254",
        "hostname": "iam-deploy-admin",
        "cloud_id": "arn:aws:iam::123456789012:role/AdminRole"
      },
      "pos": {
        "x": 720,
        "y": 280
      }
    },
    {
      "id": "node-iam-readonly",
      "label": "Billing ReadOnly IAM Role",
      "type": "IAM",
      "cvss_score": 3.5,
      "vulnerabilities": [],
      "is_crown_jewel": false,
      "status": "secure",
      "refs": {
        "hostname": "iam-billing-ro",
        "cloud_id": "arn:aws:iam::123456789012:role/BillingReadOnly"
      },
      "pos": {
        "x": 720,
        "y": 420
      }
    },
    {
      "id": "node-redis-cache",
      "label": "Session Redis Cluster",
      "type": "Database",
      "cvss_score": 7.1,
      "vulnerabilities": [
        "CVE-2023-41056"
      ],
      "is_crown_jewel": false,
      "status": "secure",
      "refs": {
        "ip": "10.0.99.5",
        "hostname": "redis-session-prod",
        "cloud_id": "i-0a1b2c3d4e5f00006"
      },
      "pos": {
        "x": 940,
        "y": 160
      }
    },
    {
      "id": "node-prod-db",
      "label": "Customer Production DB",
      "type": "Database",
      "cvss_score": 9.8,
      "vulnerabilities": [
        "CVE-2024-0012"
      ],
      "is_crown_jewel": true,
      "status": "secure",
      "refs": {
        "ip": "10.0.99.10",
        "hostname": "rds-prod-customers",
        "cloud_id": "i-0a1b2c3d4e5f00007"
      },
      "pos": {
        "x": 940,
        "y": 320
      }
    }
  ],
  "edges": [
    {
      "id": "edge-01",
      "source": "node-printer-01",
      "target": "node-dev-laptop",
      "protocol": "SSH",
      "exploit_time_sec": 12,
      "status": "open"
    },
    {
      "id": "edge-02",
      "source": "node-printer-01",
      "target": "node-file-share",
      "protocol": "SMB",
      "exploit_time_sec": 18,
      "status": "open"
    },
    {
      "id": "edge-03",
      "source": "node-printer-01",
      "target": "node-badge-reader",
      "protocol": "Telnet",
      "exploit_time_sec": 10,
      "status": "open"
    },
    {
      "id": "edge-04",
      "source": "node-badge-reader",
      "target": "node-hvac-ctrl",
      "protocol": "Telnet",
      "exploit_time_sec": 9,
      "status": "open"
    },
    {
      "id": "edge-05",
      "source": "node-badge-reader",
      "target": "node-sre-workstation",
      "protocol": "HTTPS",
      "exploit_time_sec": 20,
      "status": "open"
    },
    {
      "id": "edge-06",
      "source": "node-hvac-ctrl",
      "target": "node-finance-pc",
      "protocol": "SMB",
      "exploit_time_sec": 16,
      "status": "open"
    },
    {
      "id": "edge-07",
      "source": "node-hvac-ctrl",
      "target": "node-file-share",
      "protocol": "SMB",
      "exploit_time_sec": 15,
      "status": "open"
    },
    {
      "id": "edge-08",
      "source": "node-dev-laptop",
      "target": "node-bastion",
      "protocol": "SSH",
      "exploit_time_sec": 10,
      "status": "open"
    },
    {
      "id": "edge-09",
      "source": "node-dev-laptop",
      "target": "node-build-srv",
      "protocol": "SSH",
      "exploit_time_sec": 11,
      "status": "open"
    },
    {
      "id": "edge-10",
      "source": "node-dev-laptop",
      "target": "node-iam-admin",
      "protocol": "IAM_Trust",
      "exploit_time_sec": 8,
      "status": "open"
    },
    {
      "id": "edge-11",
      "source": "node-dev-laptop",
      "target": "node-api-gw",
      "protocol": "HTTPS",
      "exploit_time_sec": 14,
      "status": "open"
    },
    {
      "id": "edge-12",
      "source": "node-sre-workstation",
      "target": "node-bastion",
      "protocol": "SSH",
      "exploit_time_sec": 8,
      "status": "open"
    },
    {
      "id": "edge-13",
      "source": "node-sre-workstation",
      "target": "node-build-srv",
      "protocol": "HTTPS",
      "exploit_time_sec": 12,
      "status": "open"
    },
    {
      "id": "edge-14",
      "source": "node-sre-workstation",
      "target": "node-k8s-worker",
      "protocol": "SSH",
      "exploit_time_sec": 14,
      "status": "open"
    },
    {
      "id": "edge-15",
      "source": "node-sre-workstation",
      "target": "node-iam-admin",
      "protocol": "IAM_Trust",
      "exploit_time_sec": 9,
      "status": "open"
    },
    {
      "id": "edge-16",
      "source": "node-finance-pc",
      "target": "node-file-share",
      "protocol": "SMB",
      "exploit_time_sec": 10,
      "status": "open"
    },
    {
      "id": "edge-17",
      "source": "node-finance-pc",
      "target": "node-iam-readonly",
      "protocol": "IAM_Trust",
      "exploit_time_sec": 12,
      "status": "open"
    },
    {
      "id": "edge-18",
      "source": "node-finance-pc",
      "target": "node-api-gw",
      "protocol": "HTTPS",
      "exploit_time_sec": 18,
      "status": "open"
    },
    {
      "id": "edge-19",
      "source": "node-bastion",
      "target": "node-k8s-worker",
      "protocol": "SSH",
      "exploit_time_sec": 9,
      "status": "open"
    },
    {
      "id": "edge-20",
      "source": "node-bastion",
      "target": "node-build-srv",
      "protocol": "SSH",
      "exploit_time_sec": 10,
      "status": "open"
    },
    {
      "id": "edge-21",
      "source": "node-build-srv",
      "target": "node-iam-admin",
      "protocol": "IAM_Trust",
      "exploit_time_sec": 6,
      "status": "open"
    },
    {
      "id": "edge-22",
      "source": "node-build-srv",
      "target": "node-k8s-worker",
      "protocol": "HTTPS",
      "exploit_time_sec": 11,
      "status": "open"
    },
    {
      "id": "edge-23",
      "source": "node-api-gw",
      "target": "node-k8s-worker",
      "protocol": "HTTPS",
      "exploit_time_sec": 10,
      "status": "open"
    },
    {
      "id": "edge-24",
      "source": "node-api-gw",
      "target": "node-redis-cache",
      "protocol": "HTTPS",
      "exploit_time_sec": 13,
      "status": "open"
    },
    {
      "id": "edge-25",
      "source": "node-file-share",
      "target": "node-build-srv",
      "protocol": "SMB",
      "exploit_time_sec": 14,
      "status": "open"
    },
    {
      "id": "edge-26",
      "source": "node-file-share",
      "target": "node-iam-readonly",
      "protocol": "IAM_Trust",
      "exploit_time_sec": 15,
      "status": "open"
    },
    {
      "id": "edge-27",
      "source": "node-k8s-worker",
      "target": "node-redis-cache",
      "protocol": "HTTPS",
      "exploit_time_sec": 8,
      "status": "open"
    },
    {
      "id": "edge-28",
      "source": "node-k8s-worker",
      "target": "node-prod-db",
      "protocol": "HTTPS",
      "exploit_time_sec": 16,
      "status": "open"
    },
    {
      "id": "edge-29",
      "source": "node-iam-admin",
      "target": "node-prod-db",
      "protocol": "HTTPS",
      "exploit_time_sec": 10,
      "status": "open"
    },
    {
      "id": "edge-30",
      "source": "node-redis-cache",
      "target": "node-prod-db",
      "protocol": "HTTPS",
      "exploit_time_sec": 12,
      "status": "open"
    }
  ]
}
```

## 3. Core Backend Modules (`/backend`)

### `/backend/graph_state.py` (Task A1)
```python
import copy
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("breach_domino.graph_state")


class GraphState:
    def __init__(self, topology_path: Optional[Path] = None):
        self.topology_path = topology_path
        self._initial_graph = self._load_initial_topology()
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: Dict[str, Dict[str, Any]] = {}
        self.reset()

    def _load_initial_topology(self) -> Dict[str, Any]:
        if self.topology_path and self.topology_path.exists():
            try:
                with open(self.topology_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(
                        "Loaded topology from %s (%d nodes, %d edges)",
                        self.topology_path,
                        len(data.get("nodes", [])),
                        len(data.get("edges", [])),
                    )
                    return data
            except Exception as exc:
                logger.warning("Failed to load %s (%s)", self.topology_path, exc)
        return {"nodes": [], "edges": []}

    def reset(self) -> None:
        fresh = copy.deepcopy(self._initial_graph)
        self.nodes = {n["id"]: n for n in fresh.get("nodes", [])}
        self.edges = {e["id"]: e for e in fresh.get("edges", [])}

    def snapshot(self) -> Dict[str, Any]:
        return {
            "nodes": list(self.nodes.values()),
            "edges": list(self.edges.values()),
        }

    def apply_event(self, event: Dict[str, Any]) -> bool:
        etype = event.get("type")
        target_id = event.get("id")
        payload = event.get("payload") or {}

        if not etype or not target_id:
            logger.warning("Invalid GraphEvent missing type or id: %s", event)
            return False

        if etype == "node_added":
            self.nodes[target_id] = {"id": target_id, **payload}
            return True
        elif etype == "node_removed":
            if target_id not in self.nodes:
                return False
            self.nodes.pop(target_id, None)
            return True
        elif etype == "node_updated":
            if target_id not in self.nodes:
                return False
            self.nodes[target_id].update(payload)
            return True
        elif etype == "node_compromised":
            if target_id not in self.nodes:
                return False
            self.nodes[target_id]["status"] = "compromised"
            self.nodes[target_id].update(payload)
            return True
        elif etype == "cve_found":
            if target_id not in self.nodes:
                return False
            node = self.nodes[target_id]
            new_cves = payload.get("vulnerabilities", [])
            merged = list(dict.fromkeys(node.get("vulnerabilities", []) + new_cves))
            node["vulnerabilities"] = merged
            if "cvss_score" in payload:
                node["cvss_score"] = payload["cvss_score"]
            return True
        elif etype == "edge_added":
            self.edges[target_id] = {"id": target_id, **payload}
            return True
        elif etype == "edge_removed":
            if target_id not in self.edges:
                return False
            self.edges.pop(target_id, None)
            return True
        elif etype == "edge_updated":
            if target_id not in self.edges:
                return False
            self.edges[target_id].update(payload)
            return True
        elif etype == "edge_active_attack":
            if target_id not in self.edges:
                return False
            self.edges[target_id]["status"] = "active_attack"
            self.edges[target_id].update(payload)
            return True

        logger.warning("Unhandled GraphEvent type: %s", etype)
        return False
```

### `/backend/resolver.py` (Task A3)
```python
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("breach_domino.resolver")


class AssetResolver:
    def __init__(self, manual_map_path: Optional[Path] = None):
        self.manual_map_path = manual_map_path
        self._manual_map: Dict[str, str] = {}
        self._dynamic_map: Dict[str, str] = {}
        self._load_manual_map()

    def _load_manual_map(self) -> None:
        if self.manual_map_path and self.manual_map_path.exists():
            try:
                with open(self.manual_map_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    self._manual_map = {str(k).strip().lower(): str(v) for k, v in raw.items()}
                    logger.info("Loaded %d manual asset mappings from %s", len(self._manual_map), self.manual_map_path)
            except Exception as exc:
                logger.warning("Could not read manual_map.json (%s)", exc)

    def rebuild_from_graph(self, graph: Dict[str, Any]) -> None:
        mapping: Dict[str, str] = {}
        for node in graph.get("nodes", []):
            nid = node.get("id")
            if not nid:
                continue
            mapping[nid.lower()] = nid
            if node.get("label"):
                mapping[str(node["label"]).strip().lower()] = nid
            refs = node.get("refs") or {}
            for ref_key in ("ip", "hostname", "cloud_id"):
                val = refs.get(ref_key)
                if val:
                    mapping[str(val).strip().lower()] = nid
        self._dynamic_map = mapping

    def resolve(self, identifier: Optional[str]) -> Optional[str]:
        if not identifier:
            return None
        key = str(identifier).strip().lower()
        node_id = self._dynamic_map.get(key) or self._manual_map.get(key)
        if not node_id:
            logger.warning("Unknown asset identifier '%s' — logged and dropped", identifier)
            return None
        return node_id
```

### `/backend/bus.py` (Task A1)
```python
import asyncio
import logging
from typing import Set, Dict, Any
from fastapi import WebSocket

from graph_state import GraphState
from resolver import AssetResolver

logger = logging.getLogger("breach_domino.bus")


class EventBus:
    def __init__(self, state: GraphState, resolver: AssetResolver):
        self.state = state
        self.resolver = resolver
        self.clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)
        await ws.send_json({
            "kind": "snapshot",
            "graph": self.state.snapshot()
        })
        logger.info("Browser WS client connected (%d active)", len(self.clients))

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)
        logger.info("Browser WS client disconnected (%d active)", len(self.clients))

    async def publish(self, event: Dict[str, Any]) -> bool:
        async with self._lock:
            applied = self.state.apply_event(event)
            if not applied:
                logger.debug("Skipped event (target missing or invalid): %s", event)
                return False

            if event.get("type") in ("node_added", "node_updated", "node_removed"):
                self.resolver.rebuild_from_graph(self.state.snapshot())

            msg = {"kind": "event", "event": event}
            await self._broadcast(msg)
            return True

    async def broadcast_snapshot(self) -> None:
        async with self._lock:
            self.resolver.rebuild_from_graph(self.state.snapshot())
            await self._broadcast({
                "kind": "snapshot",
                "graph": self.state.snapshot()
            })

    async def _broadcast(self, message: Dict[str, Any]) -> None:
        stale: Set[WebSocket] = set()
        for ws in list(self.clients):
            try:
                await ws.send_json(message)
            except Exception:
                stale.add(ws)
        for ws in stale:
            self.clients.discard(ws)
```

## 4. Source Adapters (`/backend/adapters`)

### `/backend/adapters/replay.py` (Task A2 — DO FIRST)
```python
import asyncio
import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from bus import EventBus

logger = logging.getLogger("breach_domino.replay")


class ReplayAdapter:
    def __init__(self, bus: EventBus, events_path: Path):
        self.bus = bus
        self.events_path = events_path
        self.speed: float = 1.0
        self._running: bool = False
        self._paused: bool = False
        self._index: int = 0
        self._task: Optional[asyncio.Task] = None
        self._events: List[Dict[str, Any]] = self._load_events()

    def _load_events(self) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        if not self.events_path.exists():
            logger.warning("Replay file %s not found", self.events_path)
            return events
        with open(self.events_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        logger.info("Loaded %d replay events from %s", len(events), self.events_path)
        return events

    async def handle_control(self, msg: Dict[str, Any]) -> None:
        action = msg.get("action")
        if "speed" in msg and msg["speed"]:
            self.speed = max(float(msg["speed"]), 0.1)

        if action == "start":
            self._paused = False
            if not self._running:
                if self._index >= len(self._events):
                    self._index = 0
                self._running = True
                self._task = asyncio.create_task(self._run_loop())
        elif action == "pause":
            self._paused = True
        elif action == "reset":
            self._paused = True
            self._running = False
            if self._task and not self._task.done():
                self._task.cancel()
            self._index = 0
            self.bus.state.reset()
            await self.bus.broadcast_snapshot()

    async def _run_loop(self) -> None:
        try:
            while self._running and self._index < len(self._events):
                if self._paused:
                    await asyncio.sleep(0.05)
                    continue

                current_event = dict(self._events[self._index])
                current_event["ts"] = int(time.time() * 1000)
                current_event["source"] = "replay"
                await self.bus.publish(current_event)

                next_idx = self._index + 1
                if next_idx < len(self._events):
                    t_curr = self._events[self._index].get("ts", 0)
                    t_next = self._events[next_idx].get("ts", t_curr + 1500)
                    delta_sec = max((t_next - t_curr) / 1000.0, 0.02) / self.speed
                    await asyncio.sleep(delta_sec)

                self._index = next_idx
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False
```

### `/backend/adapters/cloud.py` (Task A4)
```python
import asyncio
import logging
import os
import time
from typing import Dict, Any, Tuple

from bus import EventBus

logger = logging.getLogger("breach_domino.cloud")

PORT_TO_PROTOCOL = {
    22: "SSH",
    443: "HTTPS",
    80: "HTTPS",
    445: "SMB",
    23: "Telnet",
}


class CloudAdapter:
    def __init__(self, bus: EventBus, poll_interval_sec: int = 45):
        self.bus = bus
        self.poll_interval_sec = poll_interval_sec
        self._last_nodes: Dict[str, Dict[str, Any]] = {}
        self._last_edges: Dict[str, Dict[str, Any]] = {}

    async def run(self) -> None:
        try:
            import boto3  # noqa: F401
        except ImportError:
            logger.warning("boto3 not installed; CloudAdapter idle")
            return

        region = os.getenv("AWS_REGION", "us-east-1")
        logger.info("Starting CloudAdapter polling every %ds in region %s", self.poll_interval_sec, region)

        while True:
            try:
                nodes, edges = await asyncio.to_thread(self._fetch_aws_topology, region)
                await self.diff_and_emit(nodes, edges)
            except Exception as exc:
                logger.warning("Cloud poll cycle failed: %s", exc)
            await asyncio.sleep(self.poll_interval_sec)

    def _fetch_aws_topology(self, region: str) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        import boto3
        session = boto3.Session(region_name=region)
        ec2 = session.client("ec2")

        nodes: Dict[str, Dict[str, Any]] = {}
        edges: Dict[str, Dict[str, Any]] = {}
        sg_to_nodes: Dict[str, list] = {}

        reservations = ec2.describe_instances().get("Reservations", [])
        for res in reservations:
            for inst in res.get("Instances", []):
                iid = inst["InstanceId"]
                name = next((t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"), iid)
                ip = inst.get("PrivateIpAddress") or inst.get("PublicIpAddress")
                hostname = inst.get("PrivateDnsName")
                node = {
                    "id": iid,
                    "label": name,
                    "type": "Database" if "db" in name.lower() else "Server",
                    "cvss_score": 5.0,
                    "vulnerabilities": [],
                    "is_crown_jewel": "prod-db" in name.lower(),
                    "status": "secure",
                    "refs": {"ip": ip, "hostname": hostname, "cloud_id": iid},
                }
                nodes[iid] = node
                for sg in inst.get("SecurityGroups", []):
                    sg_to_nodes.setdefault(sg["GroupId"], []).append(iid)

        sgs = ec2.describe_security_groups().get("SecurityGroups", [])
        for sg in sgs:
            target_sgid = sg["GroupId"]
            for perm in sg.get("IpPermissions", []):
                port = perm.get("FromPort")
                protocol = PORT_TO_PROTOCOL.get(port, "HTTPS")
                for pair in perm.get("UserIdGroupPairs", []):
                    src_sg = pair.get("GroupId")
                    for src_node in sg_to_nodes.get(src_sg, []):
                        for dst_node in sg_to_nodes.get(target_sgid, []):
                            if src_node != dst_node:
                                eid = f"edge-{src_node}-{dst_node}-{protocol}"
                                edges[eid] = {
                                    "id": eid,
                                    "source": src_node,
                                    "target": dst_node,
                                    "protocol": protocol,
                                    "exploit_time_sec": 10,
                                    "status": "open",
                                }
        return nodes, edges

    async def diff_and_emit(self, nodes: Dict[str, Dict[str, Any]], edges: Dict[str, Dict[str, Any]]) -> None:
        now_ms = int(time.time() * 1000)
        for nid, node in nodes.items():
            if nid not in self._last_nodes:
                await self.bus.publish({"type": "node_added", "id": nid, "payload": node, "ts": now_ms, "source": "cloud"})
            elif self._last_nodes[nid] != node:
                await self.bus.publish({"type": "node_updated", "id": nid, "payload": node, "ts": now_ms, "source": "cloud"})

        for nid in list(self._last_nodes.keys()):
            if nid not in nodes:
                await self.bus.publish({"type": "node_removed", "id": nid, "ts": now_ms, "source": "cloud"})

        for eid, edge in edges.items():
            if eid not in self._last_edges:
                await self.bus.publish({"type": "edge_added", "id": eid, "payload": edge, "ts": now_ms, "source": "cloud"})
            elif self._last_edges[eid] != edge:
                await self.bus.publish({"type": "edge_updated", "id": eid, "payload": edge, "ts": now_ms, "source": "cloud"})

        for eid in list(self._last_edges.keys()):
            if eid not in edges:
                await self.bus.publish({"type": "edge_removed", "id": eid, "ts": now_ms, "source": "cloud"})

        self._last_nodes = dict(nodes)
        self._last_edges = dict(edges)
```

### `/backend/adapters/ws_source.py` (Task A5)
```python
import asyncio
import json
import logging
import os
import time
from typing import Dict, Any, Optional

from bus import EventBus
from resolver import AssetResolver

logger = logging.getLogger("breach_domino.ws_source")


class WebSocketSourceAdapter:
    def __init__(self, bus: EventBus, resolver: AssetResolver, upstream_url: Optional[str] = None):
        self.bus = bus
        self.resolver = resolver
        self.upstream_url = upstream_url or os.getenv("UPSTREAM_WS_URL", "")

    async def run(self) -> None:
        if not self.upstream_url:
            logger.info("UPSTREAM_WS_URL not set; WebSocketSourceAdapter idle")
            return

        try:
            import websockets
        except ImportError:
            logger.warning("websockets package not installed; WebSocketSourceAdapter idle")
            return

        backoff = 1.0
        max_backoff = 30.0

        while True:
            try:
                logger.info("Connecting to upstream WebSocket: %s", self.upstream_url)
                async with websockets.connect(self.upstream_url) as ws:
                    backoff = 1.0
                    async for raw_msg in ws:
                        event = self.normalize_message(raw_msg)
                        if event:
                            await self.bus.publish(event)
            except Exception as exc:
                logger.warning("Upstream WS disconnected (%s). Reconnecting in %.1fs...", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, max_backoff)

    def normalize_message(self, raw_msg: str) -> Optional[Dict[str, Any]]:
        try:
            data = json.loads(raw_msg)
        except Exception:
            logger.warning("Invalid JSON from upstream WS: %s", raw_msg)
            return None

        if "type" in data and "id" in data:
            resolved_id = self.resolver.resolve(data["id"]) or data["id"]
            return {
                "type": data["type"],
                "id": resolved_id,
                "payload": data.get("payload", {}),
                "ts": int(data.get("ts") or time.time() * 1000),
                "source": "ws",
            }

        host = data.get("host") or data.get("ip") or data.get("asset_id")
        node_id = self.resolver.resolve(host)
        if not node_id:
            return None

        event_type = data.get("event_type", "node_compromised")
        return {
            "type": event_type,
            "id": node_id,
            "payload": data.get("payload", {"status": "compromised"}),
            "ts": int(time.time() * 1000),
            "source": "ws",
        }
```

### `/backend/adapters/siem.py` (Task A6)
```python
import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional

from bus import EventBus
from resolver import AssetResolver

logger = logging.getLogger("breach_domino.siem")


class SIEMAdapter:
    def __init__(self, bus: EventBus, resolver: AssetResolver, log_path: Optional[Path] = None):
        self.bus = bus
        self.resolver = resolver
        self.log_path = log_path

    def parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        line = line.strip()
        if not line:
            return None

        now_ms = int(time.time() * 1000)

        try:
            record = json.loads(line)
            src_host = record.get("src_ip") or record.get("src_host")
            dst_host = record.get("dst_ip") or record.get("dst_host") or record.get("host")
            alert_kind = str(record.get("alert", "compromise")).lower()

            if "pivot" in alert_kind or "lateral" in alert_kind:
                src_id = self.resolver.resolve(src_host)
                dst_id = self.resolver.resolve(dst_host)
                if src_id and dst_id:
                    for eid, edge in self.bus.state.edges.items():
                        if edge.get("source") == src_id and edge.get("target") == dst_id:
                            return {
                                "type": "edge_active_attack",
                                "id": eid,
                                "payload": {"status": "active_attack"},
                                "ts": now_ms,
                                "source": "siem",
                            }

            target_node = self.resolver.resolve(dst_host or src_host)
            if not target_node:
                return None

            if "cve" in record:
                return {
                    "type": "cve_found",
                    "id": target_node,
                    "payload": {
                        "vulnerabilities": [record["cve"]],
                        "cvss_score": float(record.get("cvss", 7.5)),
                    },
                    "ts": now_ms,
                    "source": "siem",
                }

            return {
                "type": "node_compromised",
                "id": target_node,
                "payload": {"status": "compromised"},
                "ts": now_ms,
                "source": "siem",
            }
        except json.JSONDecodeError:
            parts = dict(token.split("=", 1) for token in line.split() if "=" in token)
            if parts.get("src") and parts.get("dst"):
                src_id = self.resolver.resolve(parts["src"])
                dst_id = self.resolver.resolve(parts["dst"])
                if src_id and dst_id:
                    for eid, edge in self.bus.state.edges.items():
                        if edge.get("source") == src_id and edge.get("target") == dst_id:
                            return {
                                "type": "edge_active_attack",
                                "id": eid,
                                "payload": {"status": "active_attack"},
                                "ts": now_ms,
                                "source": "siem",
                            }
            host = parts.get("host") or parts.get("ip") or parts.get("dst")
            node_id = self.resolver.resolve(host)
            if not node_id:
                return None
            return {
                "type": "node_compromised",
                "id": node_id,
                "payload": {"status": "compromised"},
                "ts": now_ms,
                "source": "siem",
            }

    async def tail_file(self) -> None:
        if not self.log_path:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.touch(exist_ok=True)
        logger.info("Tailing SIEM log file at %s", self.log_path)

        with open(self.log_path, "r", encoding="utf-8") as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if not line:
                    await asyncio.sleep(0.25)
                    continue
                event = self.parse_line(line)
                if event:
                    await self.bus.publish(event)
```

## 5. FastAPI Application, Standalone Inspector & Test Suite

### `/backend/main.py` (Tasks A1 & A7 + Built-in `/demo` Test Console)
Includes a built-in standalone browser inspector at `http://localhost:8000/demo` so you can test `/ws` snapshots, click **Start / Pause / Reset / 2x Replay**, and fire live SIEM alerts in your browser without needing Person B or C's frontend.
```python
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from bus import EventBus
from graph_state import GraphState
from resolver import AssetResolver
from adapters.replay import ReplayAdapter
from adapters.cloud import CloudAdapter
from adapters.ws_source import WebSocketSourceAdapter
from adapters.siem import SIEMAdapter

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("breach_domino.main")

BASE_DIR = Path(__file__).resolve().parent
SHARED_DIR = BASE_DIR.parent / "shared"

SOURCE_MODE = os.getenv("SOURCE", "replay").lower()

state = GraphState(topology_path=SHARED_DIR / "topology.sample.json")
resolver = AssetResolver(manual_map_path=SHARED_DIR / "manual_map.json")
resolver.rebuild_from_graph(state.snapshot())

bus = EventBus(state=state, resolver=resolver)
replay_adapter = ReplayAdapter(bus=bus, events_path=SHARED_DIR / "sample_events.jsonl")
cloud_adapter = CloudAdapter(bus=bus, poll_interval_sec=int(os.getenv("CLOUD_POLL_SEC", "45")))
ws_source_adapter = WebSocketSourceAdapter(bus=bus, resolver=resolver)
siem_adapter = SIEMAdapter(
    bus=bus,
    resolver=resolver,
    log_path=Path(os.getenv("SIEM_LOG_PATH", str(BASE_DIR / "siem_alerts.log"))),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    bg_tasks = []
    logger.info("Starting Breach Domino Backend in SOURCE=%s mode", SOURCE_MODE)
    if SOURCE_MODE == "live":
        bg_tasks.append(asyncio.create_task(cloud_adapter.run()))
        bg_tasks.append(asyncio.create_task(ws_source_adapter.run()))
        bg_tasks.append(asyncio.create_task(siem_adapter.tail_file()))
    yield
    for t in bg_tasks:
        t.cancel()


app = FastAPI(title="Breach Domino Simulator Backend (Person A)", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "source_mode": SOURCE_MODE,
        "nodes": len(state.nodes),
        "edges": len(state.edges),
        "connected_clients": len(bus.clients),
    }


@app.post("/siem/ingest")
async def ingest_siem_line(payload: Dict[str, str] = Body(...)) -> Dict[str, Any]:
    line = payload.get("line", "")
    event = siem_adapter.parse_line(line)
    if not event:
        return {"accepted": False, "reason": "unresolved_or_invalid"}
    await bus.publish(event)
    return {"accepted": True, "event": event}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await bus.connect(ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if msg.get("kind") == "replay_control":
                await replay_adapter.handle_control(msg)
    except WebSocketDisconnect:
        bus.disconnect(ws)
    except Exception as exc:
        logger.warning("WS connection error: %s", exc)
        bus.disconnect(ws)


@app.get("/demo", response_class=HTMLResponse)
async def standalone_demo_console() -> str:
    '''Standalone Backend Test Console so Person A can verify /ws snapshots, replay_control, and SIEM alerts without Person B or C.'''
    return '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Person A — Standalone Backend WS Inspector</title>
  <style>
    body { background: #0b0f19; color: #e2e8f0; font-family: ui-monospace, monospace; margin: 24px; }
    h1 { font-size: 18px; color: #38bdf8; margin-bottom: 8px; }
    .bar { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
    button { background: #1e293b; color: #f8fafc; border: 1px solid #334155; padding: 8px 14px; border-radius: 6px; cursor: pointer; }
    button:hover { background: #334155; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .card { background: #111827; border: 1px solid #1f2937; border-radius: 8px; padding: 14px; max-height: 72vh; overflow: auto; }
    .compromised { color: #f87171; font-weight: bold; }
    .secure { color: #94a3b8; }
    pre { font-size: 12px; white-space: pre-wrap; margin: 0; }
  </style>
</head>
<body>
  <h1>Breach Domino Simulator — Person A Standalone Backend Test Console</h1>
  <div class="bar">
    <button onclick="sendCtrl('start', 1)">▶ Start Replay (1x)</button>
    <button onclick="sendCtrl('start', 2)">⏩ Start Replay (2x)</button>
    <button onclick="sendCtrl('pause')">⏸ Pause</button>
    <button onclick="sendCtrl('reset')">🔄 Reset</button>
    <button onclick="sendSiem()">🚨 Inject Live SIEM Alert (10.0.10.12)</button>
  </div>
  <div class="grid">
    <div class="card"><h3>Live Graph State (<span id="counts">0 nodes</span>)</h3><div id="nodes"></div></div>
    <div class="card"><h3>WebSocket Wire Log (/ws)</h3><pre id="log"></pre></div>
  </div>
  <script>
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/ws`);
    let graph = { nodes: [], edges: [] };

    function render() {
      document.getElementById('counts').textContent = `${graph.nodes.length} nodes, ${graph.edges.length} edges`;
      document.getElementById('nodes').innerHTML = graph.nodes.map(n =>
        `<div class="${n.status}">[${n.status.toUpperCase()}] <b>${n.id}</b> — ${n.label} (CVSS ${n.cvss_score})</div>`
      ).join('');
    }
    function logMsg(obj) {
      const el = document.getElementById('log');
      el.textContent = JSON.stringify(obj) + "
" + el.textContent;
    }
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      logMsg(msg);
      if (msg.kind === 'snapshot') {
        graph = msg.graph;
      } else if (msg.kind === 'event') {
        const ev = msg.event;
        const node = graph.nodes.find(n => n.id === ev.id);
        if (node && ev.type === 'node_compromised') node.status = 'compromised';
        if (node && ev.type === 'cve_found' && ev.payload) {
          node.cvss_score = ev.payload.cvss_score || node.cvss_score;
        }
      }
      render();
    };
    function sendCtrl(action, speed) {
      ws.send(JSON.stringify({ kind: 'replay_control', action, speed }));
    }
    async function sendSiem() {
      await fetch('/siem/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ line: 'host=10.0.10.12 alert=compromise' })
      });
    }
  </script>
</body>
</html>'''
```

### `/backend/test_backend.py` (Automated Verification Suite for A1–A6)
```python
import asyncio
import json
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from main import app, state, resolver, bus, replay_adapter, cloud_adapter, ws_source_adapter, siem_adapter


class TestPersonABackend(unittest.TestCase):
    def setUp(self):
        state.reset()
        resolver.rebuild_from_graph(state.snapshot())

    def test_a1_health_and_ws_snapshot(self):
        client = TestClient(app)
        res = client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["nodes"], 15)
        self.assertEqual(data["edges"], 30)

        with client.websocket_connect("/ws") as ws:
            msg = ws.receive_json()
            self.assertEqual(msg["kind"], "snapshot")
            self.assertEqual(len(msg["graph"]["nodes"]), 15)
            self.assertEqual(len(msg["graph"]["edges"]), 30)

    def test_a2_replay_adapter_stream_and_reset(self):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            snap = ws.receive_json()
            self.assertEqual(snap["kind"], "snapshot")

            ws.send_json({"kind": "replay_control", "action": "start", "speed": 50.0})
            first_event = ws.receive_json()
            self.assertEqual(first_event["kind"], "event")
            self.assertEqual(first_event["event"]["source"], "replay")
            self.assertEqual(first_event["event"]["id"], "node-printer-01")
            self.assertEqual(first_event["event"]["type"], "node_compromised")

            ws.send_json({"kind": "replay_control", "action": "reset"})
            while True:
                msg = ws.receive_json()
                if msg["kind"] == "snapshot":
                    printer = next(n for n in msg["graph"]["nodes"] if n["id"] == "node-printer-01")
                    self.assertEqual(printer["status"], "secure")
                    break

    def test_a3_asset_resolver_and_unknown_drop(self):
        # Dynamic cloud snapshot resolution
        self.assertEqual(resolver.resolve("10.0.1.50"), "node-printer-01")
        self.assertEqual(resolver.resolve("dev-mbp-alex"), "node-dev-laptop")
        self.assertEqual(resolver.resolve("i-0a1b2c3d4e5f00007"), "node-prod-db")
        # Fallback manual_map.json alias resolution
        self.assertEqual(resolver.resolve("prod-postgres-primary"), "node-prod-db")
        # Unknown asset returns None and never crashes
        self.assertIsNone(resolver.resolve("192.168.254.999"))
        self.assertIsNone(resolver.resolve(""))

    def test_a4_cloud_adapter_diff(self):
        async def run_diff():
            await cloud_adapter.diff_and_emit(
                nodes={"i-newcloud01": {"id": "i-newcloud01", "label": "New Cloud Host", "type": "Server", "cvss_score": 5.0, "vulnerabilities": [], "is_crown_jewel": False, "status": "secure", "refs": {"ip": "10.0.50.10"}}},
                edges={},
            )
            self.assertIn("i-newcloud01", state.nodes)
            self.assertEqual(resolver.resolve("10.0.50.10"), "i-newcloud01")

        asyncio.run(run_diff())

    def test_a5_ws_source_normalization(self):
        raw = json.dumps({"host": "10.0.2.14", "event_type": "node_compromised"})
        ev = ws_source_adapter.normalize_message(raw)
        self.assertIsNotNone(ev)
        self.assertEqual(ev["id"], "node-dev-laptop")
        self.assertEqual(ev["source"], "ws")

    def test_a6_siem_adapter_formats(self):
        # JSON alert line
        ev1 = siem_adapter.parse_line('{"host": "hp-laserjet-3rd-fl", "alert": "compromise"}')
        self.assertEqual(ev1["type"], "node_compromised")
        self.assertEqual(ev1["id"], "node-printer-01")
        self.assertEqual(ev1["source"], "siem")

        # Lateral movement pivot alert line
        ev2 = siem_adapter.parse_line('{"src_ip": "10.0.1.50", "dst_ip": "10.0.2.14", "alert": "lateral_pivot"}')
        self.assertEqual(ev2["type"], "edge_active_attack")
        self.assertEqual(ev2["id"], "edge-01")

        # Key=Value syslog format via POST /siem/ingest
        client = TestClient(app)
        resp = client.post("/siem/ingest", json={"line": "host=rds-prod-customers alert=compromise"})
        self.assertTrue(resp.json()["accepted"])
        self.assertEqual(state.nodes["node-prod-db"]["status"], "compromised")


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

### `/backend/.env.example` & `/backend/run.sh` (Task A7)
```ini
SOURCE=replay
LOG_LEVEL=INFO
CLOUD_POLL_SEC=45
AWS_REGION=us-east-1
UPSTREAM_WS_URL=ws://localhost:9001/stream
SIEM_LOG_PATH=./siem_alerts.log
```

```bash
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  source .venv/bin/activate
  pip install fastapi uvicorn websockets boto3 python-dotenv
else
  source .venv/bin/activate
fi
export SOURCE="${SOURCE:-replay}"
exec uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
