"""
Crucible Core Execution Engine
Manages the adversarial agent lifecycle, attack scheduling, and event loop.
"""

import logging
import uuid
import time
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class AttackStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ABORTED = "aborted"


class AgentStatus(Enum):
    IDLE = "idle"
    ATTACKING = "attacking"
    REFLECTING = "reflecting"
    DEAD = "dead"


@dataclass
class AttackEvent:
    event_id: str
    agent_id: str
    attack_type: str
    target: str
    mutation: Dict[str, Any]
    timestamp: float
    status: AttackStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class ExecutionTrace:
    trace_id: str
    target: str
    started_at: float
    completed_at: Optional[float] = None
    events: List[AttackEvent] = field(default_factory=list)
    resilience_score: Optional[float] = None
    failure_points: List[str] = field(default_factory=list)
    blast_radius: List[str] = field(default_factory=list)
    mutations: List[Dict] = field(default_factory=list)
    replay_command: Optional[str] = None

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['events'] = [
            {**e, 'status': e['status'].value if isinstance(e['status'], AttackStatus) else e['status']}
            for e in d['events']
        ]
        return d

    def save(self, path: str):
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


@dataclass
class AgentState:
    agent_id: str
    agent_type: str
    status: AgentStatus
    fitness_score: float = 100.0
    attacks_executed: int = 0
    attacks_succeeded: int = 0
    attacks_failed: int = 0
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    lineage: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.attacks_executed == 0:
            return 0.0
        return self.attacks_succeeded / self.attacks_executed

    def update_fitness(self):
        """Fitness decays with failures, grows with successful attacks."""
        if self.attacks_executed == 0:
            return
        base = self.success_rate * 100
        recency_bonus = min(10, self.attacks_executed * 0.5)
        self.fitness_score = round(min(100.0, base + recency_bonus), 2)

    def is_alive(self) -> bool:
        return self.status != AgentStatus.DEAD

    def should_die(self) -> bool:
        """Agent dies if fitness drops below threshold after enough attempts."""
        return self.attacks_executed >= 5 and self.fitness_score < 20.0


class CrucibleEngine:
    """
    Core execution engine. Manages agents, schedules attacks,
    collects events, and produces execution traces.
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.agents: Dict[str, AgentState] = {}
        self.active_traces: Dict[str, ExecutionTrace] = {}
        self.completed_traces: List[ExecutionTrace] = []
        self.event_log: List[AttackEvent] = []
        self._running = False

    def spawn_agent(self, agent_type: str, parent_id: Optional[str] = None) -> AgentState:
        """Spawn a new adversarial agent, optionally inheriting from a parent."""
        agent_id = f"agent_{agent_type}_{uuid.uuid4().hex[:8]}"
        lineage = []
        if parent_id and parent_id in self.agents:
            lineage = self.agents[parent_id].lineage + [parent_id]

        agent = AgentState(
            agent_id=agent_id,
            agent_type=agent_type,
            status=AgentStatus.IDLE,
            lineage=lineage
        )
        self.agents[agent_id] = agent
        return agent

    def kill_agent(self, agent_id: str, reason: str = "low_fitness"):
        if agent_id in self.agents:
            self.agents[agent_id].status = AgentStatus.DEAD
            logger.info(
                "agent_terminated agent_id=%s reason=%s fitness=%s",
                agent_id, reason, self.agents[agent_id].fitness_score,
            )

    def begin_trace(self, target: str) -> ExecutionTrace:
        trace_id = f"trc_{uuid.uuid4().hex[:10]}"
        trace = ExecutionTrace(
            trace_id=trace_id,
            target=target,
            started_at=time.time()
        )
        self.active_traces[trace_id] = trace
        return trace

    def record_event(self, trace: ExecutionTrace, event: AttackEvent):
        trace.events.append(event)
        self.event_log.append(event)

        if event.agent_id in self.agents:
            agent = self.agents[event.agent_id]
            agent.attacks_executed += 1
            agent.last_active = time.time()

            if event.status == AttackStatus.SUCCESS:
                agent.attacks_succeeded += 1
            elif event.status == AttackStatus.FAILED:
                agent.attacks_failed += 1

            agent.update_fitness()

            if agent.should_die():
                self.kill_agent(agent.agent_id, "fitness_below_threshold")

    def finalize_trace(self, trace: ExecutionTrace, score: float,
                       failure_points: List[str], blast_radius: List[str]):
        trace.completed_at = time.time()
        trace.resilience_score = score
        trace.failure_points = failure_points
        trace.blast_radius = blast_radius
        trace.replay_command = f"crucible replay --trace traces/{trace.trace_id}.crucible"

        self.active_traces.pop(trace.trace_id, None)
        self.completed_traces.append(trace)
        return trace

    def get_survivors(self) -> List[AgentState]:
        """Return agents still alive, sorted by fitness."""
        return sorted(
            [a for a in self.agents.values() if a.is_alive()],
            key=lambda a: a.fitness_score,
            reverse=True
        )

    def get_dead_agents(self) -> List[AgentState]:
        """The failure cemetery."""
        return [a for a in self.agents.values() if not a.is_alive()]

    def engine_status(self) -> Dict:
        survivors = self.get_survivors()
        dead = self.get_dead_agents()
        return {
            "total_agents": len(self.agents),
            "alive": len(survivors),
            "dead": len(dead),
            "avg_fitness": round(
                sum(a.fitness_score for a in survivors) / len(survivors), 2
            ) if survivors else 0,
            "total_attacks": len(self.event_log),
            "completed_traces": len(self.completed_traces),
        }
