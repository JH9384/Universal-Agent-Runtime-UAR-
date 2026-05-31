# UAR Certification Model v1

Primary Issue: #70

## Purpose

Convert runtime evidence into operator trust.

## Inputs

- Replay Confidence
- Burn-In Score
- Runtime Health
- Contract Compliance

## Scoring

Suggested v1 weighting:

- Replay Confidence: 35%
- Burn-In Score: 35%
- Runtime Health: 20%
- Contract Compliance: 10%

## Certification Levels

Experimental:
- score < 80

Silver:
- score >= 80
- replay confidence >= 80
- burn-in completed

Gold:
- score >= 95
- replay confidence >= 95
- burn-in passed
- no critical violations

## Outputs

- certification score
- certification level
- evidence summary
- warning summary
- generated report

## Consumers

- Mission Control
- Replay Explorer
- Operator reporting
- Release certification
