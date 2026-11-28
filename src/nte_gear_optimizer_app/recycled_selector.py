"""Bounded recycled option widgets; recycled presses may never select a new ID."""

from weakref import ref

from kivy.metrics import dp, sp
from kivy.properties import ObjectProperty, StringProperty
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior

from .design_widgets import DesignButton
from .responsive_scroll import ResponsiveScrollView


class SelectorRow(RecycleDataViewBehavior, DesignButton):
    value = ObjectProperty(None, allownone=True)
    name = StringProperty('')
    owner = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        self.option_index = None
        self.pressed_value = None
        self.press_valid = False
        super().__init__(**kwargs)
        self.font_name = 'NTEText'
        self.font_size = sp(14)
        self.bind(width=lambda w, v: setattr(w, 'text_size', (v - dp(16), None)))

    def refresh_view_attrs(self, rv, index, data):
        # A touch held while a view is rebound must not select its new value,
        # even if that view later cycles back to its original option.
        if self.option_index != index or self.value != data['value']:
            self.press_valid = False
            self.state = 'normal'
        self.option_index = index
        result = super().refresh_view_attrs(rv, index, data)
        if rv.trace is not None:
            rv.trace.attach_tree(self)
        return result

    def on_press(self):
        self.pressed_value = self.value
        self.press_valid = True
        owner = self.owner() if self.owner else None
        if owner is not None and owner.performance is not None:
            touch = getattr(self, '_nte_touch_id', None)
            if touch is not None:
                owner.performance.feedback('button_pressed', touch)

    def on_release(self):
        allowed = self.press_valid and self.pressed_value == self.value
        self.press_valid = False
        owner = self.owner() if self.owner else None
        if allowed and owner is not None and owner.select_callback is not None:
            touch = getattr(self, '_nte_touch_id', None)
            try:
                owner.select_callback(self.value)
            finally:
                if owner.performance is not None and touch is not None:
                    owner.performance.action_response(touch)


class RecycledSelector(ResponsiveScrollView, RecycleView):
    def __init__(self, entries, current, callback, debug=None, **kwargs):
        self.trace = debug.trace if debug else None
        self.performance = debug.performance if debug else None
        self.select_callback = callback
        self.entries = tuple(entries)
        super().__init__(do_scroll_x=False, **kwargs)
        height = dp(88 if any('\n' in n for n, _ in entries) else 52)
        layout = RecycleBoxLayout(
            default_size=(None, height),
            default_size_hint=(1, None),
            size_hint_y=None,
            orientation='vertical',
            spacing=dp(4),
        )
        layout.bind(minimum_height=layout.setter('height'))
        self.add_widget(layout)
        self.viewclass = SelectorRow
        owner = ref(self)
        self.data = [
            {
                'value': value,
                'name': name,
                'owner': owner,
                'text': ('✓  ' if value == current else '') + name,
            }
            for name, value in entries
        ]

    def rendered_rows(self):
        return sorted(
            ((w.value, w.name, w) for w in self.layout_manager.children),
            key=lambda row: row[2].option_index,
        )

    def close(self):
        self.select_callback = None
        for _, _, widget in self.rendered_rows():
            widget.press_valid = False
