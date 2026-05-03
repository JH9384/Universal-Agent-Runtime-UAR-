import json
import logging
import uuid
from typing import List, Optional

import pydantic
from fastapi import FastAPI, HTTPException, Request, status, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, validator

from uar.core.contracts import GoalSpec
from uar.core.exceptions import UARError, ValidationError
from uar.core.planner import SimplePlanner
from uar.core.replay import run_record_from_events
from uar.core.orchestrator import build_orchestration_plan
from uar.core.validation import validate_goal, validate_skills, validate_input_path
from uar.memory.json_store import JsonRunStore
from uar.api.middleware import (
    apply_middleware, rate_limit_middleware, auth_middleware, 
    request_logging_middleware, error_handler_middleware, security
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# register skills
import uar.skills.section_sum  # noqa
import uar.skills.doc_ingest  # noqa
import uar.skills.dependency_map  # noqa
import uar.skills.sum_review  # noqa
import uar.skills.ollama_generate  # noqa

app = FastAPI(
    title="UAR API",
    description="Universal Agent Runtime API with production security features",
    version="1.0.0"
)
store = JsonRunStore()

# Apply middleware
apply_middleware(app)


class RunRequest(BaseModel):
    goal: str
    skills: Optional[List[str]] = None
    input_path: Optional[str] = None
    timeout_seconds: Optional[float] = None

    @validator('goal')
    def validate_goal_field(cls, v):
        return validate_goal(v)

    @validator('skills')
    def validate_skills_field(cls, v):
        return validate_skills(v)

    @validator('input_path')
    def validate_input_path_field(cls, v):
        return validate_input_path(v)

    @validator('timeout_seconds')
    def validate_timeout_field(cls, v):
        if v is not None:
            from uar.core.validation import validate_timeout
            return validate_timeout(v)
        return v


class RunResponse(BaseModel):
    run_id: str
    goal_id: str
    skills: List[str]
    outputs: List
    status: str
    errors: List[str]
    events: List[dict]
    final_context: dict


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    field: Optional[str] = None


def _build_goal(req: RunRequest) -> GoalSpec:
    """Build GoalSpec with proper validation and unique ID"""
    goal_id = f"api-{uuid.uuid4().hex[:8]}"
    
    metadata = {}
    if req.input_path:
        metadata["input_path"] = req.input_path
    if req.timeout_seconds:
        metadata["timeout_seconds"] = req.timeout_seconds
    
    return GoalSpec(
        id=goal_id,
        user_intent=req.goal,
        objective=req.goal,
        required_skills=req.skills or [],
        metadata=metadata,
    )


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Dependency to get current authenticated user"""
    return auth_middleware(credentials)


@app.post("/api/uar/run", response_model=RunResponse, responses={
    400: {"model": ErrorResponse, "description": "Validation error"},
    429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
@error_handler_middleware
async def run_goal(
    req: RunRequest, 
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Execute a goal and return the complete result"""
    # Apply rate limiting
    rate_limit_middleware(request, credentials)
    
    # Get user info
    user_info = auth_middleware(credentials)
    
    # Log request
    request_id = request_logging_middleware(request, user_info)
    
    try:
        goal = _build_goal(req)
        planner = SimplePlanner()
        strategy = planner.plan(goal)

        from uar.core.executor import Executor

        executor = Executor()
        timeout = req.timeout_seconds or 5.0
        result = executor.run(strategy, goal, timeout_seconds=timeout)

        store.append(result)
        logger.info(f"[{request_id}] Run completed successfully: {result.run_id}")
        
        return result
        
    except ValidationError as e:
        logger.warning(f"[{request_id}] Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(e), "field": e.field}
        )
    except UARError as e:
        logger.error(f"[{request_id}] UAR error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(e)}
        )
    except Exception as e:
        logger.error(f"[{request_id}] Unexpected error in run_goal: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Internal server error"}
        )


@app.post("/api/uar/stream", responses={
    400: {"model": ErrorResponse, "description": "Validation error"},
    429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
@error_handler_middleware
async def stream_goal(
    req: RunRequest,
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Execute a goal and stream events in real-time"""
    # Apply rate limiting
    rate_limit_middleware(request, credentials)
    
    # Get user info
    user_info = auth_middleware(credentials)
    
    # Log request
    request_id = request_logging_middleware(request, user_info)
    
    try:
        goal = _build_goal(req)
        strategy = SimplePlanner().plan(goal)

        plan = build_orchestration_plan(strategy)

        from uar.core.executor import Executor

        executor = Executor()
        timeout = req.timeout_seconds or 5.0

        def emit(event: dict) -> str:
            return f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"

        async def generate():
            events = []
            try:
                # emit orchestration graph first
                yield emit({
                    "schema_version": "uar.event.v1",
                    "type": "orchestration_plan",
                    "run_id": "pending",
                    "goal_id": strategy.goal_id,
                    "skill": None,
                    "timestamp": 0,
                    "payload": {"graph": plan.to_graph()},
                    "error": None,
                })

                for event in executor.iter_events(strategy, goal, timeout_seconds=timeout):
                    events.append(event)
                    yield emit(event)

                record = run_record_from_events(events, strategy.ordered_skills)
                store.append(record)
                
                logger.info(f"[{request_id}] Stream completed successfully: {record.run_id}")
                
            except Exception as e:
                logger.error(f"[{request_id}] Stream error: {str(e)}", exc_info=True)
                # Emit error event to client
                yield emit({
                    "schema_version": "uar.event.v1",
                    "type": "error",
                    "run_id": "unknown",
                    "goal_id": strategy.goal_id,
                    "skill": None,
                    "timestamp": 0,
                    "payload": {},
                    "error": str(e)
                })
            finally:
                # Ensure persistence even if client disconnects
                if events:
                    try:
                        record = run_record_from_events(events, strategy.ordered_skills)
                        store.append(record)
                        logger.info(f"[{request_id}] Stream persisted {len(events)} events")
                    except Exception as e:
                        logger.error(f"[{request_id}] Failed to persist stream events: {str(e)}")

        return StreamingResponse(generate(), media_type="text/event-stream")
        
    except ValidationError as e:
        logger.warning(f"[{request_id}] Stream validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(e), "field": e.field}
        )
    except UARError as e:
        logger.error(f"[{request_id}] Stream UAR error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(e)}
        )
    except Exception as e:
        logger.error(f"[{request_id}] Unexpected stream error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Internal server error"}
        )


@app.get("/api/uar/runs", responses={
    429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
@error_handler_middleware
async def list_runs(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """List all stored runs"""
    # Apply rate limiting
    rate_limit_middleware(request, credentials)
    
    # Get user info
    user_info = auth_middleware(credentials)
    
    # Log request
    request_id = request_logging_middleware(request, user_info)
    
    try:
        runs = store.list_records()
        logger.info(f"[{request_id}] Listed {len(runs)} runs")
        return runs
        
    except Exception as e:
        logger.error(f"[{request_id}] Error listing runs: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to retrieve runs"}
        )


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/api/status")
async def get_status(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Get system status and user info"""
    user_info = auth_middleware(credentials)
    
    return {
        "status": "operational",
        "user": user_info,
        "available_skills": [
            "section_sum", "doc_ingest", "dependency_map", 
            "sum_review", "ollama_generate"
        ]
    }
