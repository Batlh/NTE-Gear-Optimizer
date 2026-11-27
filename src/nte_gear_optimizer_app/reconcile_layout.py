"""Kivy container that reconciles changed children without clearing a page."""

from kivy.uix.boxlayout import BoxLayout
from .page_reconcile import reconcile_children


class ReconcileLayout(BoxLayout):
    collecting = False

    def begin_refresh(self):
        self.pending_children = []
        self.collecting = True

    def add_widget(self, widget, *args, **kwargs):
        if self.collecting:
            self.pending_children.append(widget)
        else:
            return super().add_widget(widget, *args, **kwargs)

    def end_refresh(self):
        self.collecting = False
        return reconcile_children(self, self.pending_children)
