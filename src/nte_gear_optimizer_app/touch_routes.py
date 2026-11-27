"""Resolve the final receiver per touch, even when forwarding is delayed."""

from collections import OrderedDict
from copy import deepcopy


class TouchRoutes:
    def __init__(self, limit=32):
        self.limit = limit
        self.routes = OrderedDict()

    def begin(self, identifier):
        identifier = str(identifier)
        self.routes[identifier] = {
            'touch_id': identifier,
            'chain': [],
            'target': None,
            'confirmed_interactive': False,
        }
        while len(self.routes) > self.limit:
            self.routes.popitem(last=False)

    def accept(self, identifier, widget, *, definitive=False):
        if identifier is None:
            return
        identifier = str(identifier)
        if identifier not in self.routes:
            self.begin(identifier)
        route = self.routes[identifier]
        if len(route['chain']) < 64:
            route['chain'].append(deepcopy(widget))
        interactive = definitive or widget.get('field') is not None
        target = route['target']
        if interactive or (
            not route['confirmed_interactive']
            and (target is None or widget.get('depth', 0) > target.get('depth', 0))
        ):
            route['target'] = deepcopy(widget)
        route['confirmed_interactive'] |= interactive

    def snapshot(self, identifier):
        return deepcopy(self.routes.get(str(identifier)))
