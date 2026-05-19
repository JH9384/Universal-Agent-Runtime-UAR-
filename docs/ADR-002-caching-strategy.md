# ADR-002: Result Caching Strategy

## Status
Accepted

## Context
The UAR system executes skills that can be:
- Computationally expensive (AI model calls)
- Repeated with identical inputs
- Time-sensitive (cache staleness matters)

Without caching, the system would:
- Repeatedly call expensive external services
- Increase costs for API calls
- Increase latency for users
- Waste resources on redundant computations

## Decision
Implement a file-based caching layer for skill execution results.

### Implementation Details

1. **Cache Module** (`uar/core/cache.py`)
   - File-based storage in `~/.uar_cache` (configurable)
   - TTL-based expiration (default: 3600 seconds)
   - LRU eviction when limits exceeded
   - Configurable max entries and max size

2. **Cache Key Generation**
   - Based on skill name, context data, and goal
   - Deterministic to ensure cache hits
   - Handles nested data structures

3. **Integration**
   - Executor checks cache before skill execution
   - Results stored in cache after successful execution
   - Cache can be enabled/disabled per request

### Configuration
- `UAR_CACHE_DIR`: Cache directory location
- `UAR_CACHE_TTL`: Time-to-live in seconds (default: 3600)
- `UAR_CACHE_MAX_ENTRIES`: Maximum cache entries (default: 1000)
- `UAR_CACHE_MAX_SIZE`: Maximum cache size in bytes (default: 100MB)

## Consequences

### Positive
- Reduces redundant API calls
- Improves response times for cache hits
- Lowers operational costs
- Reduces load on external services
- Improves user experience

### Negative
- Cache staleness if TTL too long
- Disk space usage for cache storage
- Complexity in cache key generation
- Potential for cache poisoning if not validated
- File I/O overhead for cache operations

### Alternatives Considered
1. **In-memory cache**: Would not persist across restarts
2. **Redis cache**: Would add infrastructure dependency
3. **No cache**: Would waste resources on redundant calls

## References
- Implementation: `uar/core/cache.py`
- Integration: `uar/core/executor.py`
