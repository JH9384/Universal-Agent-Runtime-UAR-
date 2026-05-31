# Mission Control Specification

Status: Specification  
Primary Issue: #72  
Related Issue: #55

## Purpose

Mission Control is the primary operator surface for UAR.

Mission Control answers:

> What is happening right now?

## First-Class Signals

### Runtime Health

Derived from:

- health APIs
- readiness APIs
- circuit breaker status
- metrics health

### Replay Confidence

Derived from:

- Replay Confidence Model v1

### Certification Status

Derived from:

- Certification Engine
- Certification Scoring

### Active Runs

Derived from:

- run APIs
- execution state
- streaming events

### Topology State

Derived from:

- topology graph
- graph analytics
- runtime relationships

### Alerts

Derived from:

- runtime warnings
- confidence warnings
- certification failures
- health failures

### Live Event Feed

Derived from:

- SSE
- WebSocket

## Operator Personas

### Runtime Operator

Focus:

- health
- runs
- alerts

### Investigator

Focus:

- replay
- timeline
- topology

### Architect

Focus:

- certification
- guarantees
- capability inventory

## Layout

Top:
- Health
- Confidence
- Certification

Center:
- Active Runs
- Topology
- Event Feed

Bottom:
- Alerts
- Warnings
- Violations

## Drill Down Targets

Mission Control links to:

- Replay Explorer
- Topology Explorer
- Certification Center
- Runtime Library

## Success Criteria

Mission Control is complete when an operator can understand runtime state without reading logs or source code.
