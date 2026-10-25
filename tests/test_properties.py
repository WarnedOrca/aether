"""Property tests P1-P9 driven by Hypothesis (SPEC.md section 12).

Hypothesis picks seeds, approval behaviors, and blank-cell rates; the case
functions in interpreter/props.py build data and check the properties.
"""

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from interpreter import props

SETTINGS = settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@pytest.mark.parametrize("name", sorted(props.EXAMPLES.procedures))
@SETTINGS
@given(seed=st.integers(0, 10**6), behavior=st.sampled_from(props.BEHAVIORS),
       empty_rate=st.sampled_from([0.0, 0.1, 0.3]))
def test_p1_to_p4_p7_p8_p9(name, seed, behavior, empty_rate):
    assert props.run_case(name, seed, behavior, empty_rate) == []


@SETTINGS
@given(seed=st.integers(0, 10**6), kind=st.sampled_from(props.TAMPER))
def test_p5_batch_binding(seed, kind):
    assert props.batch_tamper_case(seed, kind) == []


@settings(max_examples=60, deadline=None)
@given(seed=st.integers(0, 10**6))
def test_p6_policy_thresholds(seed):
    assert props.policy_case(seed) == []
