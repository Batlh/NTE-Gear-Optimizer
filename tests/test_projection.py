from nte_gear_optimizer.projection.lv80 import project


def test_exact_minimum_raw_and_isolation():
    x = {
        'ActualTotal': '1000',
        'WhiteCurrent': '100',
        'White80': '200',
        'EquipmentPercent': '20',
        'WhiteBasis': 'IN_GAME_WHITE_WITH_PROGRESS',
    }
    original = x.copy()
    assert project(x)['ProjectedLv80Exact'] == '1120' and x == original
    assert project({**x, 'EquipmentPercent': None})['ProjectedLv80Minimum'] == '1100'
    assert project({**x, 'EquipmentPercent': None})['ProjectedLv80Exact'] is None
    assert (
        project({**x, 'WhiteBasis': 'RAW_LEVEL_STAT'})['ProjectionReason']
        == 'RAW_LEVEL_STAT_NOT_WHITE_BASIS'
    )


def test_mutant_missing_percent_as_zero_killed():
    x = {
        'ActualTotal': '1000',
        'WhiteCurrent': '100',
        'White80': '200',
        'WhiteBasis': 'IN_GAME_WHITE_WITH_PROGRESS',
    }
    assert project(x)['ProjectedLv80Exact'] is None
    assert project({**x, 'EquipmentPercent': '0'})['ProjectedLv80Exact'] == '1100'
