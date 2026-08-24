"""
Gemini Structured Planner Client for Animus Smart Room.
Constructs structured prompts with sanitized RoomState and Capability Catalogs,
requests strongly-typed GeminiStructuredPlan output, and runs deterministic validation.
STRICTLY ZERO hardware execution — data generation and validation ONLY.
"""

from __future__ import annotations
import json
import logging
import os
from typing import Any, Dict, Optional, Union

from capability_registry import UnifiedCapabilityRegistry
from room_state.models import RoomState
from planner.models import GeminiStructuredPlan, ValidationResult
from planner.validator import PlanValidator
from planner.errors import (
    GeminiApiUnavailableError,
    GeminiResponseError
)

logger = logging.getLogger("music_daemon.planner.gemini_client")

# Optional Google GenAI SDK import
try:
    from google import genai
    from google.genai import types
    HAS_GENAI_SDK = True
except ImportError:
    HAS_GENAI_SDK = False


PLANNER_SYSTEM_INSTRUCTION = """
You are the AI Planner for Animus Smart Room.
Your role is to translate natural language user intents into structured, validated plans.

CRITICAL OPERATIONAL RULES:
1. You do NOT execute hardware commands. You generate declarative structured plans only.
2. You must NEVER invent device capabilities. Use ONLY the supplied canonical capability catalog.
3. You must respect physical device bounds:
   - AC Temperature: 16°C to 30°C (Integers only). Modes: COOL, AUTO, DRY, FAN. (HEAT is unsupported).
   - PC Volume: 0% to 100% (Integers only).
   - Projector Brightness: 1% to 100% (Integers only).
4. You must treat UNKNOWN and STALE state as uncertain. Never assume an action has succeeded or state is reached unless verified.
5. You must NEVER output shell commands, Python code, PowerShell, ADB commands, UDP packets, COM calls, or raw file paths.
6. Express all actions strictly as canonical capability IDs with validated parameter objects.
7. Return only a valid JSON object strictly matching the GeminiStructuredPlan schema.
""".strip()


class GeminiPlannerClient:
    """
    Client for generating structured room orchestration plans via Google Gemini.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        registry: Optional[UnifiedCapabilityRegistry] = None,
        validator: Optional[PlanValidator] = None
    ):
        self.api_key = (
            api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        )
        self.model_name = (
            model_name
            or os.environ.get("GEMINI_PLANNER_MODEL")
            or "gemini-2.5-flash"
        )
        self.registry = registry or UnifiedCapabilityRegistry()
        self.validator = validator or PlanValidator(registry=self.registry)
        self._sdk_client = None

        if HAS_GENAI_SDK and self.api_key:
            try:
                self._sdk_client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize GenAI client: {e}")

    @property
    def is_available(self) -> bool:
        """Returns True if the Gemini API is configured and ready."""
        return bool(self.api_key)

    def build_prompt_payload(
        self,
        user_request: str,
        room_state: RoomState,
        context: Optional[Union[Dict[str, Any], Any]] = None,
        preferences: Optional[Union[Dict[str, Any], Any]] = None
    ) -> str:
        """
        Assembles structured prompt with sanitized RoomState, Capability Catalog, Context, and Preferences.
        """
        ctx_dict = context.to_dict() if hasattr(context, "to_dict") else (context or {})
        pref_dict = preferences.to_dict() if hasattr(preferences, "to_dict") else (preferences or {})

        payload = {
            "user_request": user_request,
            "room_state": room_state.to_sanitized_prompt_dict(),
            "available_capabilities": self.registry.export_prompt_schema_dict(),
            "context": ctx_dict,
            "preferences": pref_dict
        }
        return json.dumps(payload, indent=2)

    def generate_plan(
        self,
        user_request: str,
        room_state: RoomState,
        context: Optional[Dict[str, Any]] = None,
        preferences: Optional[Dict[str, Any]] = None
    ) -> GeminiStructuredPlan:
        """
        Calls Gemini API with structured output schema and parses the response into GeminiStructuredPlan.
        """
        if not self.is_available:
            raise GeminiApiUnavailableError(
                "Gemini API key is not configured. Set GEMINI_API_KEY in environment or pass api_key to client."
            )

        if not HAS_GENAI_SDK or self._sdk_client is None:
            raise GeminiApiUnavailableError(
                "Google GenAI SDK (google-genai) is not installed on this host."
            )

        user_content = self.build_prompt_payload(user_request, room_state, context, preferences)

        try:
            config = types.GenerateContentConfig(
                system_instruction=PLANNER_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=GeminiStructuredPlan,
                temperature=0.1
            )
            response = self._sdk_client.models.generate_content(
                model=self.model_name,
                contents=user_content,
                config=config
            )
            
            raw_text = response.text
            if not raw_text:
                raise GeminiResponseError("Gemini returned an empty response.")

            parsed_dict = json.loads(raw_text)
            parsed_dict["user_request"] = user_request
            return GeminiStructuredPlan.model_validate(parsed_dict)

        except Exception as e:
            if isinstance(e, (GeminiApiUnavailableError, GeminiResponseError)):
                raise
            raise GeminiResponseError(f"Failed to generate structured plan from Gemini: {e}") from e

    def generate_and_validate_plan(
        self,
        user_request: str,
        room_state: RoomState,
        context: Optional[Dict[str, Any]] = None,
        preferences: Optional[Dict[str, Any]] = None,
        current_time: Optional[float] = None
    ) -> ValidationResult:
        """
        End-to-end planning pipeline:
        1. Generate plan via Gemini (or raise error)
        2. Run deterministic validation against RoomState & Capabilities
        3. Return ValidationResult (NO HARDWARE EXECUTION).
        """
        plan = self.generate_plan(user_request, room_state, context, preferences)
        return self.validator.validate_plan(plan, room_state=room_state, current_time=current_time)
