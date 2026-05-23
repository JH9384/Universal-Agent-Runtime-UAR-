import json
from pathlib import Path

from uar.core.certification import (
    normalize_event,
    normalize_trace,
    traces_equivalent,
)

FIXTURE_DIR = Path(__file__).parent / 'fixtures'


def load_fixture(name: str):
    return json.loads((FIXTURE_DIR / name).read_text())


def test_normalize_event_strips_volatile_fields():
    event = {
        'type': 'skill_complete',
        'timestamp': 123.45,
        'correlation_id': 'abc',
        'run_id': 'run-1',
        'goal_id': 'goal-1',
    }

    normalized = normalize_event(event)

    assert 'timestamp' not in normalized
    assert 'correlation_id' not in normalized
    assert normalized['run_id'] == 'run-1'


def test_normalize_event_can_normalize_ids():
    event = {
        'run_id': 'run-1',
        'goal_id': 'goal-1',
    }

    normalized = normalize_event(event, normalize_ids=True)

    assert normalized['run_id'] == 'normalized-run'
    assert normalized['goal_id'] == 'normalized-goal'


def test_normalize_trace_preserves_event_order():
    trace = [
        {'type': 'start', 'timestamp': 1.0},
        {'type': 'complete', 'timestamp': 2.0},
    ]

    normalized = normalize_trace(trace)

    assert [event['type'] for event in normalized] == [
        'start',
        'complete',
    ]


def test_fixture_trace_is_equivalent_to_itself_after_normalization():
    trace = load_fixture('runtime_trace_success.json')

    assert traces_equivalent(trace, trace)


def test_traces_with_different_timestamps_are_equivalent():
    left = load_fixture('runtime_trace_success.json')
    right = load_fixture('runtime_trace_success.json')

    right[0]['timestamp'] = 999.0
    right[1]['timestamp'] = 1000.0

    assert traces_equivalent(left, right)


def test_traces_with_different_ids_can_be_normalized():
    left = load_fixture('runtime_trace_success.json')
    right = load_fixture('runtime_trace_success.json')

    for event in right:
        event['run_id'] = 'another-run'
        event['goal_id'] = 'another-goal'

    assert traces_equivalent(left, right, normalize_ids=True)


def test_different_event_payloads_are_not_equivalent():
    left = load_fixture('runtime_trace_success.json')
    right = load_fixture('runtime_trace_success.json')

    right[2]['payload']['result']['summary'] = 'Changed'

    assert not traces_equivalent(left, right)
