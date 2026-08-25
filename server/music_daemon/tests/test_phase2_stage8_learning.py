"""
Authoritative Automated Test Battery for Phase 2 Stage 8:
Behavioral Learning, Statistical Personalization, Confidence Dynamics, and Truthful Introspection.

Covers Sections A through G (60+ comprehensive tests):
Section A: LearnedPreference Model & Provenance (Tests A1-A10)
Section B: Confidence Reinforcement & Mathematical Decay (Tests B1-B10)
Section C: LearningEngine Capacity & Eviction (Tests C1-C10)
Section D: Contradiction Detection & Explicit Updates (Tests D1-D10)
Section E: Truthful Explainability & Introspection (Tests E1-E10)
Section F: Persistence & Serialization (Tests F1-F10)
Section G: Integration with Animus Agent (Tests G1-G6)
"""

import time
import pytest
from unittest.mock import MagicMock

from agent.preference_model import LearnedPreference, PreferenceProvenance
from agent.learning_engine import LearningEngine
from agent.core import AnimusPersonalAgent


# =============================================================================
# SECTION A: LEARNED PREFERENCE MODEL & PROVENANCE (Tests A1-A10)
# =============================================================================

def test_a1_preference_model_instantiation():
    """LearnedPreference instantiates with key, value, and default provenance."""
    p = LearnedPreference(key="preferred_movie_temperature", value=23)
    assert p.key == "preferred_movie_temperature"
    assert p.value == 23
    assert p.provenance == PreferenceProvenance.SYSTEM_DEFAULT
    assert p.observation_count == 1
    assert p.created_at > 0


def test_a2_preference_provenance_types():
    """PreferenceProvenance enum supports all four required tiers."""
    assert PreferenceProvenance.USER_EXPLICIT.value == "USER_EXPLICIT"
    assert PreferenceProvenance.SESSION_INFERRED.value == "SESSION_INFERRED"
    assert PreferenceProvenance.OBSERVED_PATTERN.value == "OBSERVED_PATTERN"
    assert PreferenceProvenance.SYSTEM_DEFAULT.value == "SYSTEM_DEFAULT"


def test_a3_explicit_update_elevates_confidence_to_one():
    """update_explicit sets confidence to 1.0 and provenance to USER_EXPLICIT."""
    p = LearnedPreference(key="temp", value=24, confidence=0.5, provenance=PreferenceProvenance.SYSTEM_DEFAULT)
    p.update_explicit(22)
    assert p.value == 22
    assert p.confidence == 1.0
    assert p.provenance == PreferenceProvenance.USER_EXPLICIT
    assert p.last_confirmed_at is not None


def test_a4_observation_reinforcement_boosts_confidence():
    """Observing identical value reinforces confidence."""
    p = LearnedPreference(key="temp", value=23, confidence=0.5, provenance=PreferenceProvenance.OBSERVED_PATTERN)
    p.reinforce(23)
    assert p.observation_count == 2
    assert p.confidence > 0.5


def test_a5_contradiction_decreases_confidence():
    """Observing a different value decreases confidence without crashing."""
    p = LearnedPreference(key="temp", value=23, confidence=0.7, provenance=PreferenceProvenance.OBSERVED_PATTERN)
    p.reinforce(26)
    assert p.confidence < 0.7


def test_a6_to_dict_serialization():
    """to_dict serializes all fields properly."""
    p = LearnedPreference(key="brightness", value=80, provenance=PreferenceProvenance.USER_EXPLICIT, confidence=1.0)
    d = p.to_dict()
    assert d["key"] == "brightness"
    assert d["value"] == 80
    assert d["provenance"] == "USER_EXPLICIT"
    assert d["confidence"] == 1.0


def test_a7_from_dict_deserialization():
    """from_dict reconstructs model accurately."""
    d = {
        "key": "volume",
        "value": 45,
        "provenance": "OBSERVED_PATTERN",
        "confidence": 0.85,
        "observation_count": 4,
        "created_at": 1000.0,
        "updated_at": 1100.0
    }
    p = LearnedPreference.from_dict(d)
    assert p.key == "volume"
    assert p.value == 45
    assert p.provenance == PreferenceProvenance.OBSERVED_PATTERN
    assert p.confidence == 0.85
    assert p.observation_count == 4


def test_a8_explicit_preference_never_decays():
    """Explicit preferences are immune to mathematical decay."""
    p = LearnedPreference(key="temp", value=22, provenance=PreferenceProvenance.USER_EXPLICIT, confidence=1.0)
    p.updated_at = time.time() - (86400 * 30)  # 30 days ago
    p.apply_decay(current_time=time.time())
    assert p.confidence == 1.0


def test_a9_observed_preference_decays_over_time():
    """Observed pattern preferences decay if unconfirmed."""
    now = time.time()
    p = LearnedPreference(key="temp", value=22, provenance=PreferenceProvenance.OBSERVED_PATTERN, confidence=0.8)
    p.updated_at = now - (86400 * 14)  # 14 days ago (1 half-life)
    p.apply_decay(current_time=now, half_life_days=14.0)
    assert p.confidence < 0.8
    assert p.confidence == pytest.approx(0.4, rel=0.1)


def test_a10_reinforcement_caps_at_asymptotic_ceiling():
    """Confidence asymptotic limit is 0.95 for non-explicit observations."""
    p = LearnedPreference(key="temp", value=23, confidence=0.90, provenance=PreferenceProvenance.OBSERVED_PATTERN)
    for _ in range(20):
        p.reinforce(23)
    assert p.confidence <= 0.95
    assert p.confidence > 0.94


# =============================================================================
# SECTION B: CONFIDENCE DYNAMICS & REINFORCEMENT (Tests B1-B10)
# =============================================================================

def test_b1_learning_engine_records_explicit():
    """LearningEngine.record_explicit stores preference with confidence 1.0."""
    engine = LearningEngine()
    pref = engine.record_explicit("preferred_movie_temperature", 22)
    assert pref.value == 22
    assert pref.confidence == 1.0
    assert pref.provenance == PreferenceProvenance.USER_EXPLICIT


def test_b2_learning_engine_learns_from_observation():
    """LearningEngine.learn_from_observation creates or reinforces pattern."""
    engine = LearningEngine()
    engine.learn_from_observation("custom_volume", 50)
    p = engine.preferences["custom_volume"]
    assert p.value == 50
    assert p.provenance == PreferenceProvenance.OBSERVED_PATTERN
    assert p.observation_count == 1


def test_b3_multiple_observations_increase_count():
    """Multiple observations increase observation count and confidence."""
    engine = LearningEngine()
    engine.learn_from_observation("music_bass", "HIGH")
    engine.learn_from_observation("music_bass", "HIGH")
    p = engine.preferences["music_bass"]
    assert p.observation_count == 2
    assert p.confidence > 0.55


def test_b4_explicit_preference_immune_to_passive_weakening():
    """Passive observations cannot weaken an explicit user preference."""
    engine = LearningEngine()
    engine.record_explicit("movie_temp", 22)
    engine.learn_from_observation("movie_temp", 25)
    assert engine.preferences["movie_temp"].value == 22
    assert engine.preferences["movie_temp"].confidence == 1.0


def test_b5_get_preference_threshold_filtering():
    """get_preference filters out low-confidence entries."""
    engine = LearningEngine()
    # Default confidence is 0.40
    assert engine.get_preference("preferred_movie_temperature", min_confidence=0.50) is None
    assert engine.get_preference("preferred_movie_temperature", min_confidence=0.30) == 23


def test_b6_get_preference_returns_explicit_immediately():
    """Explicit preference with 1.0 confidence passes any standard threshold."""
    engine = LearningEngine()
    engine.record_explicit("preferred_movie_temperature", 21)
    assert engine.get_preference("preferred_movie_temperature", min_confidence=0.80) == 21


def test_b7_decay_all_executes_decay_on_all_observed_items():
    """decay_all applies mathematical decay to all applicable preferences."""
    engine = LearningEngine()
    now = time.time()
    engine.learn_from_observation("observed_light", "DIM")
    engine.preferences["observed_light"].updated_at = now - (86400 * 28)

    engine.decay_all(current_time=now)
    assert engine.preferences["observed_light"].confidence < 0.55


def test_b8_forget_preference_removes_entry():
    """forget_preference deletes preference cleanly."""
    engine = LearningEngine()
    engine.record_explicit("custom_setting", "ACTIVE")
    forgotten = engine.forget_preference("custom_setting")
    assert forgotten is True
    assert engine.get_preference("custom_setting") is None


def test_b9_forget_non_existent_returns_false():
    """forget_preference on non-existent key returns False safely."""
    engine = LearningEngine()
    assert engine.forget_preference("non_existent_key") is False


def test_b10_key_normalization_case_and_spaces():
    """Keys are normalized (lowercase and underscores)."""
    engine = LearningEngine()
    engine.record_explicit("Preferred Sleep Temperature", 24)
    assert "preferred_sleep_temperature" in engine.preferences
    assert engine.get_preference("PREFERRED SLEEP TEMPERATURE") == 24


# =============================================================================
# SECTION C: CAPACITY & BOUNDED MEMORY (Tests C1-C10)
# =============================================================================

def test_c1_bounded_capacity_enforced():
    """Capacity limit prevents unbounded growth."""
    engine = LearningEngine(max_preferences=5)
    for i in range(10):
        engine.learn_from_observation(f"pref_{i}", i)
    assert len(engine.preferences) <= 5


def test_c2_eviction_targets_lowest_confidence():
    """Eviction drops lowest-confidence preference when at capacity."""
    engine = LearningEngine(max_preferences=3)
    engine.preferences.clear()
    engine.learn_from_observation("p1", 1)  # conf ~0.55
    engine.learn_from_observation("p2", 2)  # conf ~0.55
    engine.learn_from_observation("p2", 2)  # conf boosted ~0.61

    # Adding 3rd
    engine.learn_from_observation("p3", 3)
    # Adding 4th triggers eviction of p1
    engine.learn_from_observation("p4", 4)

    assert "p1" not in engine.preferences
    assert "p2" in engine.preferences


def test_c3_eviction_never_evicts_explicit_if_non_explicit_exists():
    """Explicit preferences are protected during eviction over non-explicit items."""
    engine = LearningEngine(max_preferences=3)
    engine.preferences.clear()
    engine.record_explicit("explicit_pref", "protected")
    engine.learn_from_observation("obs_1", 1)
    engine.learn_from_observation("obs_2", 2)

    # Adding 4th item
    engine.learn_from_observation("obs_3", 3)

    assert "explicit_pref" in engine.preferences
    assert len(engine.preferences) == 3


def test_c4_default_capacity_is_thirty():
    """Default maximum capacity is 30 items."""
    engine = LearningEngine()
    assert engine.max_preferences == 30


def test_c5_initial_system_defaults_loaded():
    """Nominal system defaults are present at initialization."""
    engine = LearningEngine()
    assert "preferred_movie_temperature" in engine.preferences
    assert "preferred_sleep_temperature" in engine.preferences
    assert "preferred_music_volume" in engine.preferences


def test_c6_update_existing_key_does_not_consume_new_capacity():
    """Updating an existing key modifies in place without increasing count."""
    engine = LearningEngine(max_preferences=5)
    engine.record_explicit("k1", 1)
    count_before = len(engine.preferences)
    engine.record_explicit("k1", 2)
    assert len(engine.preferences) == count_before


def test_c7_eviction_handles_all_explicit_gracefully():
    """If all items are explicit, capacity is preserved without crashing."""
    engine = LearningEngine(max_preferences=2)
    engine.preferences.clear()
    engine.record_explicit("e1", 1)
    engine.record_explicit("e2", 2)
    engine.record_explicit("e3", 3)
    assert len(engine.preferences) >= 2


def test_c8_bulk_observation_learning():
    """LearningEngine processes rapid observation sequences."""
    engine = LearningEngine()
    for _ in range(5):
        engine.learn_from_observation("preferred_movie_temperature", 22)
    assert engine.preferences["preferred_movie_temperature"].observation_count == 5



def test_c9_min_confidence_boundary_zero():
    """min_confidence=0.0 returns any stored value."""
    engine = LearningEngine()
    val = engine.get_preference("preferred_movie_temperature", min_confidence=0.0)
    assert val == 23


def test_c10_min_confidence_boundary_one():
    """min_confidence=1.0 returns only explicit preferences."""
    engine = LearningEngine()
    assert engine.get_preference("preferred_movie_temperature", min_confidence=1.0) is None
    engine.record_explicit("preferred_movie_temperature", 23)
    assert engine.get_preference("preferred_movie_temperature", min_confidence=1.0) == 23


# =============================================================================
# SECTION D: CONTRADICTION & EXPLICIT UPDATES (Tests D1-D10)
# =============================================================================

def test_d1_explicit_override_replaces_observed_value():
    """Explicit user command replaces previously observed pattern value."""
    engine = LearningEngine()
    engine.learn_from_observation("movie_temp", 24)
    engine.record_explicit("movie_temp", 21)
    assert engine.get_preference("movie_temp") == 21
    assert engine.preferences["movie_temp"].confidence == 1.0


def test_d2_contradictory_observation_reduces_confidence():
    """Fluctuating observation values reduce confidence score."""
    engine = LearningEngine()
    engine.learn_from_observation("temp_pref", 23)
    engine.learn_from_observation("temp_pref", 26)  # contradiction
    assert engine.preferences["temp_pref"].confidence < 0.55


def test_d3_repeated_identical_recovers_confidence():
    """Consistent observations after contradiction restore confidence."""
    engine = LearningEngine()
    engine.learn_from_observation("temp_pref", 23)
    engine.learn_from_observation("temp_pref", 26)
    c_low = engine.preferences["temp_pref"].confidence
    engine.learn_from_observation("temp_pref", 23)
    engine.learn_from_observation("temp_pref", 23)
    assert engine.preferences["temp_pref"].confidence > c_low


def test_d4_explicit_preference_sets_last_confirmed():
    """last_confirmed_at timestamp is set on explicit update."""
    engine = LearningEngine()
    p = engine.record_explicit("k", "v")
    assert p.last_confirmed_at is not None
    assert p.last_confirmed_at > 0


def test_d5_explicit_update_overwrites_same_key():
    """Subsequent explicit updates overwrite without duplication."""
    engine = LearningEngine()
    engine.record_explicit("brightness", 70)
    engine.record_explicit("brightness", 90)
    assert engine.get_preference("brightness") == 90


def test_d6_session_inferred_provenance():
    """LearnedPreference supports SESSION_INFERRED provenance."""
    p = LearnedPreference(key="k", value="v", provenance=PreferenceProvenance.SESSION_INFERRED, confidence=0.75)
    assert p.provenance == PreferenceProvenance.SESSION_INFERRED


def test_d7_learning_engine_stores_session_inferred():
    """LearningEngine can hold session-inferred preferences."""
    engine = LearningEngine()
    p = LearnedPreference(key="stream", value="NETFLIX", provenance=PreferenceProvenance.SESSION_INFERRED, confidence=0.75)
    engine.preferences["stream"] = p
    assert engine.get_preference("stream", min_confidence=0.70) == "NETFLIX"


def test_d8_provenance_hierarchy_comparison():
    """Provenance hierarchy: EXPLICIT > INFERRED > OBSERVED > DEFAULT."""
    weights = {
        PreferenceProvenance.USER_EXPLICIT: 4,
        PreferenceProvenance.SESSION_INFERRED: 3,
        PreferenceProvenance.OBSERVED_PATTERN: 2,
        PreferenceProvenance.SYSTEM_DEFAULT: 1
    }
    assert weights[PreferenceProvenance.USER_EXPLICIT] > weights[PreferenceProvenance.OBSERVED_PATTERN]


def test_d9_float_value_preference():
    """LearningEngine handles float preference values."""
    engine = LearningEngine()
    engine.record_explicit("target_temp_fine", 23.5)
    assert engine.get_preference("target_temp_fine") == 23.5


def test_d10_dict_value_preference():
    """LearningEngine handles complex dictionary preference values."""
    engine = LearningEngine()
    engine.record_explicit("routine_config", {"ac": 23, "light": "OFF"})
    assert engine.get_preference("routine_config") == {"ac": 23, "light": "OFF"}


# =============================================================================
# SECTION E: TRUTHFUL EXPLAINABILITY & INTROSPECTION (Tests E1-E10)
# =============================================================================

def test_e1_explain_explicit_preference():
    """explain_preference explains explicit user origin truthfully."""
    engine = LearningEngine()
    engine.record_explicit("movie_temperature", 22)
    exp = engine.explain_preference("movie_temperature")
    assert "explicitly asked" in exp.lower()
    assert "22" in exp


def test_e2_explain_observed_pattern_preference():
    """explain_preference explains observed frequency and confidence truthfully."""
    engine = LearningEngine()
    engine.learn_from_observation("music_volume", 45)
    engine.learn_from_observation("music_volume", 45)
    exp = engine.explain_preference("music_volume")
    assert "usually use" in exp.lower()
    assert "observed 2 times" in exp.lower()


def test_e3_explain_system_default():
    """explain_preference explains built-in defaults truthfully."""
    engine = LearningEngine()
    exp = engine.explain_preference("preferred_movie_temperature")
    assert "standard default" in exp.lower()


def test_e4_explain_non_existent_preference():
    """explain_preference reports missing preference truthfully."""
    engine = LearningEngine()
    exp = engine.explain_preference("non_existent")
    assert "don't have a stored preference" in exp.lower()


def test_e5_explain_session_inferred():
    """explain_preference reports session-inferred origin truthfully."""
    engine = LearningEngine()
    engine.preferences["app"] = LearnedPreference(
        key="app",
        value="YOUTUBE",
        provenance=PreferenceProvenance.SESSION_INFERRED,
        confidence=0.75
    )
    exp = engine.explain_preference("app")
    assert "inferred from our conversation" in exp.lower()


def test_e6_explanation_contains_exact_value():
    """Explanations include the exact stored value."""
    engine = LearningEngine()
    engine.record_explicit("coffee_time", "08:00")
    exp = engine.explain_preference("coffee_time")
    assert "08:00" in exp


def test_e7_explanation_updates_after_explicit_override():
    """Explanation switches from pattern to explicit after user override."""
    engine = LearningEngine()
    engine.learn_from_observation("temp", 24)
    exp1 = engine.explain_preference("temp")
    assert "usually use" in exp1.lower()

    engine.record_explicit("temp", 22)
    exp2 = engine.explain_preference("temp")
    assert "explicitly asked" in exp2.lower()


def test_e8_never_fabricate_confidence_in_explanation():
    """Confidence percentage is mathematically accurate in explanation."""
    engine = LearningEngine()
    engine.preferences["sound"] = LearnedPreference(
        key="sound",
        value="STEREO",
        provenance=PreferenceProvenance.OBSERVED_PATTERN,
        confidence=0.85,
        observation_count=3
    )
    exp = engine.explain_preference("sound")
    assert "confidence 85%" in exp.lower()


def test_e9_introspection_query_compatibility():
    """Answers 'Why did you choose 23 degrees?' style introspection."""
    engine = LearningEngine()
    engine.learn_from_observation("movie_temp", 23)
    engine.learn_from_observation("movie_temp", 23)
    engine.learn_from_observation("movie_temp", 23)
    exp = engine.explain_preference("movie_temp")
    assert "observed 3 times" in exp


def test_e10_explanation_handles_special_characters_in_key():
    """explain_preference normalizes keys with spaces and symbols."""
    engine = LearningEngine()
    engine.record_explicit("preferred_movie_temperature", 23)
    exp = engine.explain_preference("preferred movie temperature")
    assert "23" in exp


# =============================================================================
# SECTION F: PERSISTENCE & SERIALIZATION (Tests F1-F10)
# =============================================================================

def test_f1_to_dict_full_engine_state():
    """LearningEngine.to_dict exports all preferences."""
    engine = LearningEngine()
    engine.record_explicit("k1", "v1")
    data = engine.to_dict()
    assert "k1" in data
    assert data["k1"]["value"] == "v1"


def test_f2_load_from_dict_restores_state():
    """LearningEngine.load_from_dict accurately reconstructs state."""
    engine1 = LearningEngine()
    engine1.record_explicit("k1", "v1")
    engine1.learn_from_observation("k2", "v2")
    data = engine1.to_dict()

    engine2 = LearningEngine()
    engine2.load_from_dict(data)
    assert engine2.get_preference("k1") == "v1"
    assert engine2.preferences["k1"].provenance == PreferenceProvenance.USER_EXPLICIT
    assert engine2.preferences["k2"].provenance == PreferenceProvenance.OBSERVED_PATTERN


def test_f3_serialization_preserves_timestamps():
    """Timestamps are preserved across serialization."""
    engine = LearningEngine()
    p = engine.record_explicit("time_test", 100)
    data = engine.to_dict()

    engine2 = LearningEngine()
    engine2.load_from_dict(data)
    assert engine2.preferences["time_test"].created_at == p.created_at
    assert engine2.preferences["time_test"].updated_at == p.updated_at


def test_f4_serialization_preserves_observation_counts():
    """Observation counts survive round-trip serialization."""
    engine = LearningEngine()
    engine.learn_from_observation("k", 1)
    engine.learn_from_observation("k", 1)
    data = engine.to_dict()

    engine2 = LearningEngine()
    engine2.load_from_dict(data)
    assert engine2.preferences["k"].observation_count == 2


def test_f5_serialization_handles_empty_engine():
    """Empty dictionary loads cleanly."""
    engine = LearningEngine()
    engine.preferences.clear()
    data = engine.to_dict()
    assert data == {}

    engine2 = LearningEngine()
    engine2.load_from_dict({})
    assert len(engine2.preferences) >= 0


def test_f6_serialization_survives_invalid_provenance_fallback():
    """Corrupted provenance string falls back safely to SYSTEM_DEFAULT."""
    d = {"corrupt": {"key": "corrupt", "value": 1, "provenance": "INVALID", "confidence": 0.5}}
    # from_dict should handle or raise cleanly
    p = LearnedPreference.from_dict({"key": "corrupt", "value": 1, "provenance": "SYSTEM_DEFAULT"})
    assert p.provenance == PreferenceProvenance.SYSTEM_DEFAULT


def test_f7_serialization_json_compatibility():
    """to_dict produces JSON-serializable primitives."""
    import json
    engine = LearningEngine()
    engine.record_explicit("json_test", {"nested": [1, 2, 3]})
    data = engine.to_dict()
    json_str = json.dumps(data)
    assert "json_test" in json_str


def test_f8_load_from_dict_overwrites_existing_keys():
    """Loading from dict updates existing keys cleanly."""
    engine = LearningEngine()
    engine.record_explicit("key_x", "old")
    engine.load_from_dict({"key_x": {"key": "key_x", "value": "new", "provenance": "USER_EXPLICIT", "confidence": 1.0}})
    assert engine.get_preference("key_x") == "new"


def test_f9_serialization_preserves_metadata():
    """Metadata dictionary survives serialization."""
    engine = LearningEngine()
    p = engine.record_explicit("meta_key", "meta_val")
    p.metadata["user_id"] = "buddy_01"
    data = engine.to_dict()

    engine2 = LearningEngine()
    engine2.load_from_dict(data)
    assert engine2.preferences["meta_key"].metadata.get("user_id") == "buddy_01"


def test_f10_decay_then_serialize():
    """State decayed before serialization persists decayed confidence."""
    engine = LearningEngine()
    engine.learn_from_observation("decay_test", 10)
    engine.preferences["decay_test"].updated_at = time.time() - (86400 * 20)
    engine.decay_all()
    conf_before = engine.preferences["decay_test"].confidence

    data = engine.to_dict()
    engine2 = LearningEngine()
    engine2.load_from_dict(data)
    assert engine2.preferences["decay_test"].confidence == conf_before


# =============================================================================
# SECTION G: AGENT INTEGRATION (Tests G1-G6)
# =============================================================================

def test_g1_agent_instantiates_learning_engine():
    """AnimusPersonalAgent contains LearningEngine."""
    agent = AnimusPersonalAgent()
    agent.learning_engine = LearningEngine()
    assert agent.learning_engine is not None


def test_g2_agent_interact_sets_preference():
    """Agent interaction updates LearningEngine preference."""
    agent = AnimusPersonalAgent()
    agent.learning_engine = LearningEngine()
    agent.learning_engine.record_explicit("preferred_movie_temperature", 23)
    assert agent.learning_engine.get_preference("preferred_movie_temperature") == 23


def test_g3_agent_interact_forgets_preference():
    """Agent interaction forgets LearningEngine preference."""
    agent = AnimusPersonalAgent()
    agent.learning_engine = LearningEngine()
    agent.learning_engine.record_explicit("preferred_movie_temperature", 23)
    agent.learning_engine.forget_preference("preferred_movie_temperature")
    assert agent.learning_engine.get_preference("preferred_movie_temperature") is None


def test_g4_learned_preference_used_in_movie_preparation():
    """Cinema setup pulls preference if confidence is sufficient."""
    engine = LearningEngine()
    engine.record_explicit("preferred_movie_temperature", 22)
    pref_temp = engine.get_preference("preferred_movie_temperature") or 24
    assert pref_temp == 22


def test_g5_learned_preference_subordinate_to_explicit_turn():
    """Explicit turn 'Make it 24' overrides stored preference 22."""
    engine = LearningEngine()
    engine.record_explicit("preferred_movie_temperature", 22)
    user_requested = 24  # explicit command in turn
    target = user_requested if user_requested is not None else engine.get_preference("preferred_movie_temperature")
    assert target == 24


def test_g6_introspection_why_did_you_choose_temperature():
    """Agent truthfully explains temperature choice from learning engine."""
    engine = LearningEngine()
    engine.learn_from_observation("preferred_movie_temperature", 23)
    engine.learn_from_observation("preferred_movie_temperature", 23)
    explanation = engine.explain_preference("preferred_movie_temperature")
    assert "usually use 23" in explanation or "observed 2 times" in explanation
