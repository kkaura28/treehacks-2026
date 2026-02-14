# analysis/src/data_types.py
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


Vec3 = Tuple[float, float, float]
QuatWXYZ = Tuple[float, float, float, float]


@dataclass(frozen=True)
class Pose6D:
    """Pose in camera/world frame (whatever perception uses). Quaternion is (w, x, y, z)."""
    position: Vec3
    quaternion_wxyz: QuatWXYZ = (1.0, 0.0, 0.0, 0.0)

    def p(self) -> np.ndarray:
        return np.asarray(self.position, dtype=float)

    def q(self) -> np.ndarray:
        return np.asarray(self.quaternion_wxyz, dtype=float)


@dataclass(frozen=True)
class HandState:
    """
    joints: dict joint_name -> (x,y,z)
    side: "left" or "right"
    """
    side: str
    joints: Dict[str, Vec3] = field(default_factory=dict)
    confidence: float = 1.0

    def joint(self, name: str) -> Optional[np.ndarray]:
        v = self.joints.get(name)
        return None if v is None else np.asarray(v, dtype=float)


@dataclass(frozen=True)
class ToolState:
    tool_id: str
    pose: Pose6D
    tool_type: Optional[str] = None
    confidence: float = 1.0


@dataclass(frozen=True)
class Frame:
    t: float  # seconds
    tool: ToolState
    hands: Dict[str, HandState] = field(default_factory=dict)  # keys: "left","right"
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Event:
    event_type: str
    t_start: float
    t_end: float
    confidence: float = 1.0
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Keep JSON small/clean: drop empty meta
        if not d.get("meta"):
            d.pop("meta", None)
        return d
