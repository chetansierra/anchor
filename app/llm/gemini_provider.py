"""Gemini backend (google-genai, function calling).

Best-effort adapter: it follows the documented google-genai API but is **not
exercised by the test suite** (needs an API key) — verify against your installed
google-genai version before relying on it in production. The `google-genai` SDK
is lazy-imported in the provider class.
"""
from __future__ import annotations

from typing import Any

from .base import LLMMessage, LLMResponse, ToolCall, ToolSpec, Usage


class GeminiProvider:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        from google import genai  # lazy

        self.name = "gemini"
        self.model = model
        self._genai = genai
        self._client = genai.Client(api_key=api_key)

    def _build_tools(self, tools: list[ToolSpec] | None):
        from google.genai import types

        if not tools:
            return None
        return [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name=t.name, description=t.description, parameters=t.input_schema
                    )
                    for t in tools
                ]
            )
        ]

    def _build_contents(self, messages: list[LLMMessage]):
        from google.genai import types

        contents = []
        for msg in messages:
            if msg.role == "tool":
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_function_response(
                                name=tr.tool_call_id, response={"result": tr.content}
                            )
                            for tr in msg.tool_results
                        ],
                    )
                )
            elif msg.role == "assistant":
                parts = []
                if msg.content:
                    parts.append(types.Part(text=msg.content))
                for tc in msg.tool_calls:
                    parts.append(
                        types.Part(
                            function_call=types.FunctionCall(name=tc.name, args=tc.arguments)
                        )
                    )
                contents.append(types.Content(role="model", parts=parts))
            else:
                contents.append(
                    types.Content(role="user", parts=[types.Part(text=msg.content)])
                )
        return contents

    def generate(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            tools=self._build_tools(tools),
        )
        resp = self._client.models.generate_content(
            model=self.model, contents=self._build_contents(messages), config=config
        )
        return self._parse(resp)

    @staticmethod
    def _parse(resp: Any) -> LLMResponse:
        tool_calls: list[ToolCall] = []
        for fc in getattr(resp, "function_calls", None) or []:
            # Gemini matches results by function name, so we use it as the id.
            tool_calls.append(ToolCall(id=fc.name, name=fc.name, arguments=dict(fc.args or {})))
        text = ""
        try:
            text = (resp.text or "").strip()
        except Exception:
            text = ""
        meta = getattr(resp, "usage_metadata", None)
        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            usage=Usage(
                input_tokens=getattr(meta, "prompt_token_count", 0) or 0,
                output_tokens=getattr(meta, "candidates_token_count", 0) or 0,
            ),
            stop_reason="tool_use" if tool_calls else "end_turn",
        )
