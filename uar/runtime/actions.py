from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from fastapi import APIRouter

from uar.runtime.ws.broadcast_hub import BroadcastEnvelope, BroadcastHub

router = APIRouter()
hub = BroadcastHub()


@dataclass(slots=True)
class OperatorActionResult:
    action: str
    accepted: bool

    def to_dict(self) -> Dict[str, object]:
        return {
            "action": self.action,
            "accepted": self.accepted,
        }


@router.post('/runtime/actions/{action}')
async def run_operator_action(action: str) -> Dict[str, object]:
    result = OperatorActionResult(action=action, accepted=True)

    hub.publish(
        BroadcastEnvelope(
            channel='runtime.actions',
            event_type='operator.action.accepted',
            payload=result.to_dict(),
        )
    )

    return result.to_dict()


@router.get('/runtime/actions/events')
async def drain_operator_action_events() -> Dict[str, object]:
    return {
        "events": hub.drain(),
    }
