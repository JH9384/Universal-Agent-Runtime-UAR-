# ADR-001: Circuit Breaker Pattern for External Services

## Status
Accepted

## Context
The UAR system makes numerous calls to external AI services (OpenAI, Groq, Ollama, etc.). These services can experience:
- Temporary outages
- Rate limiting
- Network failures
- Degraded performance

Without protection, these failures can:
- Cascade through the system
- Cause timeouts for all users
- Exhaust resources (threads, connections)
- Provide poor user experience

## Decision
Implement the Circuit Breaker pattern for all external service calls.

### Implementation Details

1. **Circuit Breaker Module** (`uar/core/circuit_breaker.py`)
   - Three states: CLOSED, OPEN, HALF_OPEN
   - Configurable failure threshold
   - Configurable recovery timeout
   - Thread-safe implementation using `threading.Lock`

2. **Decorator Pattern** (`uar/core/circuit_breaker_decorator.py`)
   - `@with_circuit_breaker` decorator for easy integration
   - Global circuit breaker instances per service
   - Graceful degradation on circuit open
   - Functions to query circuit breaker states

3. **Applied to Skills**
   - OpenAI skills (chat, completion, embedding)
   - Ollama (already had manual circuit breaker)
   - Can be extended to other external services

### Configuration
- Default failure threshold: 3-5 failures
- Default recovery timeout: 30-60 seconds
- Service-specific configuration via decorator parameters

## Consequences

### Positive
- Prevents cascading failures
- Improves system resilience
- Provides graceful degradation
- Reduces resource waste on failing services
- Better user experience during outages

### Negative
- Adds complexity to skill implementation
- Requires configuration tuning per service
- May temporarily disable valid requests during recovery
- Additional monitoring needed for circuit breaker states

### Alternatives Considered
1. **Retry only**: Would continue hammering failing services
2. **Timeout only**: Would waste resources on timeouts
3. **Manual intervention**: Not scalable, requires human action

## References
- Circuit Breaker pattern: https://martinfowler.com/bliki/CircuitBreaker.html
- Implementation: `uar/core/circuit_breaker.py`
