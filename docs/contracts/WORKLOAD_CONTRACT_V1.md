# Workload Contract v1

## Purpose

Provide a universal execution contract for all workload classes.

Examples:

- Agent
- Workflow
- Research Task
- Scientific Compute Job
- Simulation
- Future Xarvus Module

The runtime should treat all of them uniformly.

---

## Required Lifecycle

Plan

Execute

Emit Events

Emit Artifacts

Return Result

---

## Required Properties

Every workload must expose:

- workload_id
- workload_type
- goal_id
- run_id

---

## Required Outputs

### Events

Must emit runtime events that conform to:

uar.event.v1

### Artifacts

May emit:

- files
- reports
- data products
- analysis outputs

### Results

Must provide:

- status
- summary
- metadata

---

## Plug-and-Play Requirement

A new workload should gain automatically:

- Mission Control visibility
- Replay support
- Runtime Health visibility
- Certification visibility
- Timeline visibility

without modifying runtime core.

---

## Success Test

If a completely new workload class can be added without modifying:

- executor kernel
- replay engine
- event schema
- mission control

then plug-and-play architecture has been achieved.
