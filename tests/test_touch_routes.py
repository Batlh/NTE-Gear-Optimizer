from nte_gear_optimizer_app.touch_routes import TouchRoutes


def test_delayed_field_target_survives_other_touch_and_outer_receivers():
    routes = TouchRoutes()
    routes.begin('A')
    routes.accept('A', {'class': 'ScrollView', 'depth': 3})
    routes.begin('B')
    routes.accept('B', {'class': 'Button', 'depth': 5, 'label': 'B'}, definitive=True)
    routes.accept(
        'A',
        {'class': 'TextInput', 'field': 'y:CycleIntensity', 'depth': 9},
        definitive=True,
    )
    routes.accept('A', {'class': 'ScrollView', 'depth': 3})
    assert routes.snapshot('A')['target']['field'] == 'y:CycleIntensity'
    assert routes.snapshot('B')['target']['label'] == 'B'
    assert len(routes.snapshot('A')['chain']) == 3


def test_disabled_hidden_actual_consumer_is_preserved_without_false_interactive_target():
    routes = TouchRoutes()
    routes.begin('A')
    routes.accept('A', {'class': 'ScrollView', 'depth': 3})
    routes.accept(
        'A', {'class': 'BoxLayout', 'depth': 8, 'enabled': False, 'tree_visible': False}
    )
    routes.accept('A', {'class': 'BoxLayout', 'depth': 1})
    assert routes.snapshot('A')['target']['enabled'] is False


def test_routes_and_chain_memory_is_bounded():
    routes = TouchRoutes(limit=3)
    for i in range(10):
        routes.begin(i)
        for j in range(100):
            routes.accept(i, {'class': 'BoxLayout', 'depth': j})
    assert len(routes.routes) == 3
    assert len(routes.snapshot(9)['chain']) == 64
