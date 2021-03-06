import random
import string
import warnings

import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_allclose
from scipy import stats

import linearmodels
from linearmodels.utility import (AttrDict, InapplicableTestStatistic, InvalidTestStatistic,
                                  WaldTestStatistic, ensure_unique_column,
                                  format_wide, has_constant, inv_sqrth, missing_warning,
                                  panel_to_frame)

MISSING_PANEL = 'Panel' not in dir(pd)


def test_missing_warning():
    missing = np.zeros(500, dtype=np.bool)
    with warnings.catch_warnings(record=True) as w:
        missing_warning(missing)
        assert len(w) == 0

    missing[0] = True
    with warnings.catch_warnings(record=True) as w:
        missing_warning(missing)
        assert len(w) == 1

    original = linearmodels.WARN_ON_MISSING
    linearmodels.WARN_ON_MISSING = False
    with warnings.catch_warnings(record=True) as w:
        missing_warning(missing)
        assert len(w) == 0
    linearmodels.WARN_ON_MISSING = original


def test_hasconstant():
    x = np.random.randn(100, 3)
    hc, loc = has_constant(x)
    assert bool(hc) is False
    assert loc is None
    x[:, 0] = 1
    hc, loc = has_constant(x)
    assert hc is True
    assert loc == 0
    x[:, 0] = 2
    hc, loc = has_constant(x)
    assert hc is True
    assert loc == 0
    x[::2, 0] = 0
    x[:, 1] = 1
    x[1::2, 1] = 0
    hc, loc = has_constant(x)
    assert hc is True


def test_wald_statistic():
    ts = WaldTestStatistic(1.0, "_NULL_", 1, name="_NAME_")
    assert str(hex(id(ts))) in ts.__repr__()
    assert '_NULL_' in str(ts)
    assert ts.stat == 1.0
    assert ts.df == 1
    assert ts.df_denom is None
    assert ts.dist_name == 'chi2(1)'
    assert isinstance(ts.critical_values, dict)
    assert_allclose(1 - stats.chi2.cdf(1.0, 1), ts.pval)

    ts = WaldTestStatistic(1.0, "_NULL_", 1, 1000, name="_NAME_")
    assert ts.df == 1
    assert ts.df_denom == 1000
    assert ts.dist_name == 'F(1,1000)'
    assert_allclose(1 - stats.f.cdf(1.0, 1, 1000), ts.pval)


def test_invalid_test_statistic():
    ts = InvalidTestStatistic('_REASON_', name='_NAME_')
    assert str(hex(id(ts))) in ts.__repr__()
    assert '_REASON_' in str(ts)
    assert np.isnan(ts.pval)
    assert ts.critical_values is None


def test_inapplicable_test_statistic():
    ts = InapplicableTestStatistic(reason='_REASON_', name='_NAME_')
    assert str(hex(id(ts))) in ts.__repr__()
    assert '_REASON_' in str(ts)
    assert np.isnan(ts.pval)
    assert ts.critical_values is None

    ts = InapplicableTestStatistic()
    assert 'not applicable' in str(ts)


def test_inv_sqrth():
    x = np.random.randn(1000, 10)
    xpx = x.T @ x
    invsq = inv_sqrth(xpx)
    prod = invsq @ xpx @ invsq - np.eye(10)
    assert_allclose(1 + prod, np.ones((10, 10)))


def test_ensure_unique_column():
    df = pd.DataFrame({'a': [0, 1, 0], 'b': [1.0, 0.0, 1.0]})
    out = ensure_unique_column('a', df)
    assert out == '_a_'
    out = ensure_unique_column('c', df)
    assert out == 'c'
    out = ensure_unique_column('a', df, '=')
    assert out == '=a='
    df['_a_'] = -1
    out = ensure_unique_column('a', df)
    assert out == '__a__'


def test_attr_dict():
    ad = AttrDict()
    ad['one'] = 'one'
    ad[1] = 1
    ad[('a', 2)] = ('a', 2)
    assert list(ad.keys()) == ['one', 1, ('a', 2)]
    assert len(ad) == 3

    ad2 = ad.copy()
    assert list(ad2.keys()) == list(ad.keys())
    assert ad.get('one', None) == 'one'
    assert ad.get('two', False) is False

    k, v = ad.popitem()
    assert k == 'one'
    assert v == 'one'

    items = ad.items()
    assert (1, 1) in items
    assert (('a', 2), ('a', 2)) in items
    assert len(items) == 2

    values = ad.values()
    assert 1 in values
    assert ('a', 2) in values
    assert len(values) == 2

    ad2 = AttrDict()
    ad2[1] = 3
    ad2['one'] = 'one'
    ad2['a'] = 'a'
    ad.update(ad2)
    assert ad[1] == 3
    assert 'a' in ad

    ad.__str__()
    with pytest.raises(AttributeError):
        ad.__ordered_dict__ = None
    with pytest.raises(AttributeError):
        ad.some_other_key
    with pytest.raises(KeyError):
        ad['__ordered_dict__'] = None

    del ad[1]
    assert 1 not in ad.keys()
    ad.new_value = 'new_value'
    assert 'new_value' in ad.keys()
    assert ad.new_value == ad['new_value']

    for key in ad.keys():
        if isinstance(key, str):
            assert key in dir(ad)

    new_value = ad.pop('new_value')
    assert new_value == 'new_value'

    del ad.one
    assert 'one' not in ad.keys()

    ad.clear()
    assert list(ad.keys()) == []


def test_format_wide():
    k = 26
    inputs = [chr(65 + i) * (20 + i) for i in range(k)]
    out = format_wide(inputs, 80)
    assert max(map(lambda v: len(v), out)) <= 80


@pytest.mark.skipif(MISSING_PANEL, reason='pd.Panel is not installed')
@pytest.mark.filterwarnings('ignore::FutureWarning')
def test_panel_to_midf():
    x = np.random.standard_normal((3, 7, 100))
    expected = pd.Panel(x).to_frame()
    df = panel_to_frame(x, list(range(3)), list(range(7)), list(range(100)))
    pd.testing.assert_frame_equal(df, expected)

    expected = pd.Panel(x).swapaxes(1, 2).to_frame(filter_observations=False)
    df = panel_to_frame(x, list(range(3)), list(range(7)), list(range(100)), True)
    pd.testing.assert_frame_equal(df, expected)
    entities = list(map(''.join, [[random.choice(string.ascii_lowercase) for __ in range(10)]
                                  for _ in range(100)]))
    times = pd.date_range('1999-12-31', freq='A-DEC', periods=7)
    var_names = ['x.{0}'.format(i) for i in range(1, 4)]
    expected = pd.Panel(x, items=var_names, major_axis=times, minor_axis=entities)
    expected = expected.swapaxes(1, 2).to_frame(filter_observations=False)
    df = panel_to_frame(x, var_names, times, entities, True)
    pd.testing.assert_frame_equal(df, expected)
