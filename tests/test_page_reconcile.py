from nte_gear_optimizer_app.page_reconcile import reconcile_children
import pytest


class Container:
    def __init__(self):
        self.children = []
        self.calls = []

    def add_widget(self, child, index=0):
        self.calls.append(('add', id(child)))
        self.children.insert(index, child)
        child.parent = self

    def remove_widget(self, child):
        self.calls.append(('remove', id(child)))
        self.children.remove(child)
        child.parent = None


class Widget:
    def __init__(self, parent=None):
        self.parent = parent


def test_unchanged_page_is_not_rebuilt_and_only_dependency_is_replaced():
    page = Container()
    a, b, c, new = [Widget() for _ in range(4)]
    reconcile_children(page, [a, b, c])
    page.calls.clear()
    assert reconcile_children(page, [a, b, c]) == 0 and not page.calls
    assert reconcile_children(page, [a, new, c]) == 2
    assert page.children == [c, new, a]
    assert all(identity not in (id(a), id(c)) for operation, identity in page.calls)
    assert b.parent is None


def test_cross_page_ownership_and_duplicate_widget_are_rejected():
    a = Widget(parent=Container())
    with pytest.raises(ValueError):
        reconcile_children(Container(), [a])
    b = Widget()
    with pytest.raises(ValueError):
        reconcile_children(Container(), [b, b])
