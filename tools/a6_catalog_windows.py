"""CI-only real Windows drags for sourced/recycled normal and synthetic lists."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

assert os.environ.get('GITHUB_ACTIONS') == 'true' and sys.platform == 'win32'
root = Path(__file__).resolve().parents[1]
metadata = root / 'BUILD_METADATA.json'
assert not metadata.exists(), 'Do not overwrite preexisting build metadata'
metadata.write_text(
    json.dumps(
        {
            'test_build': True,
            'emulator_test_only': False,
            'commit': subprocess.check_output(
                ['git', 'rev-parse', 'HEAD'], text=True
            ).strip(),
            'scope': 'Isolated CI source test, not delivered executable',
        }
    )
    + '\n',
    encoding='utf-8',
    newline='\n',
)
# Reuse the exact proven physical mouse injection methods; importing the old
# script normally would also start its full200-gesture matrix unnecessarily.
source = root / 'tools/a5_profile_windows.py'
prefix = source.read_text(encoding='utf-8').split('\napp = PerformanceProbe()')[0]
namespace = {'__file__': str(source), '__name__': '_a6_physical_driver'}
exec(compile(prefix, str(source), 'exec'), namespace)
Base = namespace['PerformanceProbe']
Clock = namespace['Clock']
Window = namespace['Window']
out = Path('build/a6_catalog_windows')
out.mkdir(parents=True, exist_ok=False)


def compact(g):
    result = {k: v for k, v in g.items() if k != 'frame_profile'}
    result['frame_profile'] = {
        k: v for k, v in g.get('frame_profile', {}).items() if k != 'rows'
    }
    return result


class CatalogProbe(Base):
    def on_start(self):
        assert Clock._max_fps == namespace['Config'].getint('graphics', 'maxfps')
        self.actions = self.scenario()
        self.failure = None
        self.drag_error = None
        self.blocks = []
        self.debug.frame_profiler.enabled = True
        Clock.schedule_once(self.advance, 1)

    def visible(self, widget, scroll):
        x, y = widget.to_window(widget.x, widget.y)
        sx, sy = scroll.to_window(scroll.x, scroll.y)
        return (
            x >= sx - 1
            and y >= sy - 1
            and x + widget.width <= sx + scroll.width + 1
            and y + widget.height <= sy + scroll.height + 1
        )

    def list_case(self, kind, entries):
        if kind == 'normal_arks':
            title = 'Ark'
            self.selector_specs[title] = (entries, self.vm.ark_id)
            self.open_selector(
                title, entries, lambda value: self.change(self.vm.choose_ark, value)
            )
        else:
            self.open_load_list(kind)
        yield 1
        _, _, scroll, _ = self.active_selector
        last = scroll.entries[-1][1]
        seen = set()
        max_attached = 0
        original = self.vm.current.copy(), self.vm.item_x.copy(), self.vm.item_y.copy()
        for _ in range(200):
            views = scroll.rendered_rows()
            seen.update(w.uid for _, _, w in views)
            max_attached = max(max_attached, len(views))
            target = next((w for key, _, w in views if key == last), None)
            if target is not None and self.visible(target, scroll):
                break
            page = self.scroll
            self.scroll = scroll
            self.drag(False)
            self.scroll = page
            yield 1.1
        else:
            raise AssertionError(('Last row unreachable', kind))
        for _ in range(60):
            effect = scroll.effect_y
            if scroll._touch is None and abs(effect.velocity) < 1:
                break
            yield 0.25
        else:
            raise AssertionError('Modal inertia failed to settle naturally')
        target = next(w for key, _, w in scroll.rendered_rows() if key == last)
        assert self.visible(target, scroll)
        assert max_attached < 40 and len(seen) < 60, (kind, max_attached, len(seen))
        Window.screenshot(name=str(out / (kind + '_last.png')))
        self.tap(target)
        yield 0.8
        assert self.active_selector is None
        if kind == 'normal_arks':
            assert self.vm.ark_id == last
        else:
            assert self.load_mode.choice == last
        assert original == (self.vm.current, self.vm.item_x, self.vm.item_y)
        gestures = [
            compact(g)
            for g in self.debug.scroll_observer.summary()['gestures']
            if g.get('scroll', '').startswith('selector:')
            and g.get('status') == 'MEASURED_GL_FLIP_PROXY'
        ]
        assert gestures, (kind, 'No measured actual scrolling')
        self.blocks.append(
            {
                'kind': kind,
                'entries': len(scroll.entries),
                'last_selected': last,
                'max_attached_rows': max_attached,
                'unique_view_widgets': len(seen),
                'gestures': gestures[-6:],
            }
        )

    def scenario(self):
        from nte_gear_optimizer_app.legacy_reference import ark_display_name

        entries = [('Nicht gewählt', None)] + [
            (ark_display_name(r), r['ArkID']) for r in self.vm.catalog['Arks']
        ]
        yield from self.list_case('normal_arks', entries)
        yield from self.list_case('arks', None)
        yield from self.list_case('inventory', None)
        for key, value in {
            'ProfileType': 'DAMAGE',
            'ScalingStat': 'ANG',
            'CritEligible': 'TRUE',
            'BreakEligible': 'TRUE',
            'CycleType': 'NONE',
        }.items():
            self.vm.set_override(key, value)
        self.vm.step = 2
        self.render()
        yield 1
        original = self.vm.current.copy(), self.vm.item_x.copy(), self.vm.item_y.copy()
        for enabled in [False, True, True, False]:
            self.set_load_mode(enabled)
            yield 1
            old = {
                g['touch_id'] for g in self.debug.scroll_observer.summary()['gestures']
            }
            for reverse in [False, True]:
                self.drag(reverse)
                yield 2
            assert original == (self.vm.current, self.vm.item_x, self.vm.item_y)
            gestures = [
                compact(g)
                for g in self.debug.scroll_observer.summary()['gestures']
                if g['touch_id'] not in old
                and g.get('status') == 'MEASURED_GL_FLIP_PROXY'
            ]
            assert gestures
            self.blocks.append(
                {'kind': 'step3', 'load_mode': enabled, 'gestures': gestures}
            )
        self.result = {'status': 'MEASURED', 'blocks': self.blocks}

    def finish(self):
        result = {
            'status': 'FAIL' if self.failure else 'MEASURED',
            'failure': self.failure,
            'blocks': self.blocks,
            'source_commit': json.loads(metadata.read_text())['commit'],
            'physical_driver_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'setup': 'Programmatic catalog/mode/profile setup, actual OS drags/taps for list/scroll evidence',
            'scope': 'Windows compositor/GL-flip proxy, not Samsung device timing',
        }
        (out / 'result.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
            newline='\n',
        )
        self.stop()


app = CatalogProbe()
app.run()
assert json.loads((out / 'result.json').read_text())['status'] == 'MEASURED'
