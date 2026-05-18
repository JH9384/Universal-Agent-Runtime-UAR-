# Dependency Compliance Status

This document tracks the compliance and version status of all UAR dependencies against their latest available versions on PyPI.

## Core Dependencies

| Package | Current Constraint | Latest Version | Status | Notes |
|---------|-------------------|----------------|--------|-------|
| fastapi | >=0.110,<1.0 | 0.136.1 | ✅ Compliant | Current constraint allows latest version |
| uvicorn | >=0.27,<1.0 | 0.47.0 | ✅ Compliant | Current constraint allows latest version |
| httpx | >=0.27,<1.0 | 0.28.1 | ✅ Compliant | Current constraint allows latest version |
| pydantic | >=2.0,<3.0 | 2.13.4 | ✅ Compliant | Current constraint allows latest version |
| pandas | >=2.0 | 3.0.3 | ✅ Compliant | Current constraint allows latest version |

## Document Processing Dependencies

| Package | Current Constraint | Latest Version | Status | Notes |
|---------|-------------------|----------------|--------|-------|
| pypdf | >=4.0 | 6.11.0 | ✅ Compliant | Current constraint allows latest version |
| python-docx | >=1.1 | 1.2.0 | ✅ Compliant | Current constraint allows latest version |
| openpyxl | >=3.1 | 3.1.5/3.2.0b1 | ✅ Compliant | Current constraint allows latest stable version |
| nbformat | >=5.9 | 5.10.4 | ✅ Compliant | Current constraint allows latest version |

## Data Processing Dependencies

| Package | Current Constraint | Latest Version | Status | Notes |
|---------|-------------------|----------------|--------|-------|
| pyarrow | >=14.0 | 24.0.0 | ✅ Compliant | Current constraint allows latest version |

## Web Dependencies

| Package | Current Constraint | Latest Version | Status | Notes |
|---------|-------------------|----------------|--------|-------|
| python-multipart | >=0.0.9 | 0.0.29 | ✅ Compliant | Current constraint allows latest version |

## Storage Dependencies

| Package | Current Constraint | Latest Version | Status | Notes |
|---------|-------------------|----------------|--------|-------|
| autonomi | Optional | 0.7.1 | ⚠️ Experimental | Network stability issues, data permanence not guaranteed until Autonomi 2.0 (early Q2 2026), Python SDK has usability and concurrency issues |

## AI/ML Dependencies

| Package | Current Constraint | Latest Version | Status | Notes |
|---------|-------------------|----------------|--------|-------|
| graphrag | >=1.0 | 3.0.9 | ✅ Compliant | Current constraint allows latest version |

## UOR Compliance Dependencies

| Package | Current Constraint | Latest Version | Status | Notes |
|---------|-------------------|----------------|--------|-------|
| rfc8785 | >=0.1.0 | 0.1.4 | ✅ Compliant | Fixed from incorrect >=1.0.0 constraint |

## Changes Made

### Critical Fixes
- **rfc8785**: Changed constraint from `>=1.0.0` to `>=0.1.0` - the latest version is 0.1.4, not 1.0.0

## Compliance Summary

All dependencies are currently compliant with their latest versions. The version constraints are appropriately set to allow updates while maintaining stability by avoiding breaking changes within major version boundaries.

## Recommendations

1. Consider tightening version constraints for production deployments to pin exact versions for reproducibility
2. Monitor for breaking changes in major version updates (e.g., Pydantic 3.0, pandas 4.0)
3. Review GraphRAG updates for potential API changes as it's rapidly evolving (currently at 3.0.9)
4. All current constraints are appropriate for development and production use

## Last Updated

May 18, 2026
