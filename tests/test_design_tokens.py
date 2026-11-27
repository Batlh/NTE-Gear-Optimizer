import hashlib, json
from pathlib import Path
from nte_gear_optimizer_app.design_tokens import TOKENS, contrast, result_sections
from nte_gear_optimizer_app.viewmodel import ComparisonViewModel
from nte_gear_optimizer_app import texts as T

ROOT = Path(__file__).resolve().parents[1]


def test_shared_tokens_are_packaged_byte_identically():
    assert (ROOT / 'design/design_tokens.json').read_bytes() == (
        ROOT / 'src/nte_gear_optimizer_app/assets/design_tokens.json'
    ).read_bytes()
    assert TOKENS['min_control_dp'] >= 48
    assert TOKENS['selector_row_dp'] == 52


def test_every_declared_text_background_pair_meets_contrast():
    for foreground, background in TOKENS['contrast_pairs']:
        assert contrast(foreground, background) >= 4.5, (
            foreground,
            background,
            contrast(foreground, background),
        )


def test_bold_font_matches_the_pinned_regular_source():
    path = ROOT / 'src/nte_gear_optimizer_app/assets/DejaVuSans-Bold.ttf'
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == 'b184b89e3c1075f22f6b71575b6fc20d4972b3cfd3b23322ca6fd596dcaef167'
    )


def test_result_cards_preserve_all_explanations_and_known_values():
    vm = ComparisonViewModel()
    vm.calculate()
    summary = vm.compact_display()
    leading, changes, guide, hints = result_sections(summary, T.CHANGED, T.HINTS)
    reconstructed = leading + '\n\n' + changes
    if guide:
        reconstructed += '\n\nGuide\n' + guide
    reconstructed += '\n\n' + T.HINTS + '\n' + hints
    assert reconstructed == summary
    assert 'Was fehlt' in leading
