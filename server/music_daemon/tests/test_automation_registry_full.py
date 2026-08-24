"""
Validation Test Suite for Automation Registry (Phase E.2).
Validates:
- Exactly 67 declarative automations across 7 categories
- Schema completeness (required_capabilities, steps, verification, risk_level)
- Service dispatcher execution coverage for all 67 automation IDs
"""

import pytest
from unittest.mock import MagicMock

from automation_registry import AutomationRegistry, AutomationCategory, RiskLevel
from firetv_service import FireTvService, ServiceResult


@pytest.fixture
def registry():
    return AutomationRegistry()


@pytest.fixture
def mock_service():
    srv = MagicMock(spec=FireTvService)
    # Return valid ServiceResult for any method called
    dummy_res = ServiceResult(
        service="test",
        success=True,
        action_taken="executed",
        truthful_status="success",
        verified=True
    )
    srv.start_cinema.return_value = dummy_res
    srv.stop_cinema.return_value = dummy_res
    srv.pause_content.return_value = dummy_res
    srv.resume_content.return_value = dummy_res
    srv.switch_provider.return_value = dummy_res
    srv.watch_content.return_value = dummy_res
    srv.route_audio_to_firetv.return_value = dummy_res
    srv.route_audio_to_pc.return_value = dummy_res
    srv.recover_bluetooth.return_value = dummy_res
    srv.recover_firetv_adb.return_value = dummy_res
    srv.recover_projector_hdmi.return_value = dummy_res
    srv.recover_stuck_app.return_value = dummy_res
    srv.recover_stopped_playback.return_value = dummy_res
    srv.full_entertainment_recovery.return_value = dummy_res
    srv.quick_break.return_value = dummy_res
    srv.resume_after_break.return_value = dummy_res
    srv.pause_for_call.return_value = dummy_res
    srv.resume_after_call.return_value = dummy_res
    srv.transition_work_to_cinema.return_value = dummy_res
    srv.transition_cinema_to_work.return_value = dummy_res
    srv.transition_music_to_cinema.return_value = dummy_res
    srv.transition_cinema_to_music.return_value = dummy_res
    srv.arriving_home.return_value = dummy_res
    srv.leaving_home.return_value = dummy_res
    srv.goodnight.return_value = dummy_res
    srv.morning_entertainment.return_value = dummy_res
    srv.shutdown_entertainment.return_value = dummy_res
    srv.sync_entertainment_state.return_value = dummy_res
    srv.emergency_mute.return_value = dummy_res
    srv.restore_audio.return_value = dummy_res
    srv.prepare_movie_session.return_value = dummy_res
    srv.prepare_music_session.return_value = dummy_res
    srv.prepare_tv_session.return_value = dummy_res
    srv.capabilities = MagicMock()
    srv.projector = MagicMock()
    srv.get_live_state.return_value = MagicMock(soundbar_connected=True)
    # Bind execute_automation to actual implementation logic
    srv.execute_automation = lambda aid, params=None: FireTvService.execute_automation(srv, aid, params)
    return srv


class TestAutomationRegistryFull:

    def test_total_automation_count_is_67(self, registry):
        assert registry.count() == 67, f"Expected 67 automations, found {registry.count()}"

    def test_all_seven_categories_populated(self, registry):
        expected_categories = {
            AutomationCategory.CINEMA: 15,
            AutomationCategory.STREAMING: 12,
            AutomationCategory.AUDIO: 10,
            AutomationCategory.PROJECTOR: 7,
            AutomationCategory.INTERRUPTION: 9,
            AutomationCategory.LIFECYCLE: 6,
            AutomationCategory.RECOVERY: 8,
        }

        total = 0
        for cat, expected_count in expected_categories.items():
            items = registry.list_by_category(cat)
            assert len(items) == expected_count, f"Category {cat.value} has {len(items)} items, expected {expected_count}"
            total += len(items)
        assert total == 67

    def test_all_automations_have_valid_metadata(self, registry):
        for auto in registry.list_all():
            assert auto.automation_id, "Automation ID must not be empty"
            assert auto.name, f"Automation {auto.automation_id} must have a name"
            assert auto.description, f"Automation {auto.automation_id} must have a description"
            assert isinstance(auto.category, AutomationCategory), f"Automation {auto.automation_id} must have valid category"
            assert isinstance(auto.risk_level, RiskLevel), f"Automation {auto.automation_id} must have valid risk level"
            assert len(auto.required_capabilities) > 0 or len(auto.steps) > 0, f"Automation {auto.automation_id} must declare capabilities or steps"
            d = auto.to_dict()
            assert d["automation_id"] == auto.automation_id
            assert "category" in d

    def test_all_67_automations_dispatch_through_service(self, registry, mock_service):
        for auto in registry.list_all():
            res = mock_service.execute_automation(auto.automation_id, {})
            assert res is not None, f"Dispatcher returned None for automation {auto.automation_id}"
            assert res.success is True, f"Dispatcher failed for automation {auto.automation_id}: {res.message}"
            assert res.error_code is None or res.error_code != "UNSUPPORTED_CAPABILITY", f"Automation {auto.automation_id} not routed in execute_automation"
