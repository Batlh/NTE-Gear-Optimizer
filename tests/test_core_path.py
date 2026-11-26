import pytest

class TestKernpfad:
    @pytest.mark.parametrize("case",['unrelated_object_error_preserves_build', 'missing_value_only_dependent_output', 'guide_baseline_panel_swap_path', 'damage_weight_not_dps_simulation', 'effective_profile', 'guide_target_basis_priority', 'lv80_projection', 'branch_override_boundary', 'context_channels', 'mode_channels', 'atomic_panel_base', 'console_validation'])
    @pytest.mark.skip(reason="Phase 1B: Arbeitsweise Rev5 §13 and v029 list Kernpfad-Grenzen; comparison port not implemented")
    def test_core_path(self,case):
        raise NotImplementedError(case)
