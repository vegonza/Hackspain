import os
import base64
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any, TypeVar, cast

from openai import OpenAI, OpenAIError
from openai.types.chat import ChatCompletionContentPartParam
from pydantic import BaseModel, ValidationError
from shared.logger import get_logger
from shared.retries import InvalidModelResponse
from shared.usage import UsageEntry, UsageRecord

MODEL = "google/gemini-3.8-flash"
PROMPTS_DIRECTORY = Path(__file__).parent / "prompts"
Result = TypeVar("Result", bound=BaseModel)
logger = get_logger()


def load_prompt(filename: str) -> str:
    return (PROMPTS_DIRECTORY / filename).read_text(encoding="utf-8").strip()


def inline_schema(schema: dict[str, Any]) -> dict[str, Any]:
    definitions = schema.get("$defs", {})

    def expand(value: Any) -> Any:
        if isinstance(value, list):
            return [expand(item) for item in value]
        if isinstance(value, dict):
            if "$ref" in value:
                definition = definitions[value["$ref"].removeprefix("#/$defs/")]
                return expand({**definition, **{key: item for key, item in value.items() if key != "$ref"}})
            return {key: expand(item) for key, item in value.items() if key != "$defs"}
        return value

    return expand(schema)


class ExtractionManager:
    def __init__(self, client: OpenAI) -> None:
        self.client = client

    def run(
        self, instruction: str, content: str, result_type: type[Result],
        usage: UsageRecord | None = None,
        page_images: Sequence[bytes] = (),
        *, model: str = MODEL, fallback_models: Sequence[str] = (),
    ) -> Result:
        models: tuple[str, ...] = (model, *fallback_models)
        for index, candidate in enumerate(models):
            try:
                return self._run_model(instruction, content, result_type, usage, page_images, candidate)
            except (OpenAIError, InvalidModelResponse) as error:
                if index == len(models) - 1:
                    raise
                logger.warning("[AI] %s failed with %s; trying %s", candidate, type(error).__name__, models[index + 1])
        raise RuntimeError("AI model chain is empty")

    def _run_model(
        self, instruction: str, content: str, result_type: type[Result],
        usage: UsageRecord | None, page_images: Sequence[bytes], model: str,
    ) -> Result:
        user_content: list[ChatCompletionContentPartParam] = [{"type": "text", "text": content}]
        for number, image in enumerate(page_images, start=1):
            user_content.extend([
                {"type": "text", "text": f"Invoice page {number}"},
                {"type": "image_url", "image_url": {
                    "url": "data:image/jpeg;base64," + base64.b64encode(image).decode("ascii"),
                    "detail": "high",
                }},
            ])
        result = self.client.chat.completions.create(
            model=model,
            stream=False,
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": user_content},
            ],
            tools=[{
                "type": "function",
                "function": {
                    "name": result_type.__name__,
                    "description": "Return the structured result for the supplied document content.",
                    "parameters": inline_schema(result_type.model_json_schema()),
                },
            }],
            tool_choice="required",
            parallel_tool_calls=False,
            extra_body={"usage": {"include": True}, "provider": {"sort": "throughput"}},
        )
        if usage is not None:
            reported_usage = result.usage.model_dump()
            provider = cast(dict[str, Any], result.model_extra)["provider"]
            usage.provider = provider
            usage.model = result.model
            usage.usage.append(UsageEntry(
                model=result.model, provider=provider,
                cost=Decimal(str(reported_usage["cost"])),
                details={"response_id": result.id, "result_type": result_type.__name__, **reported_usage},
            ))
        if not result.choices:
            raise InvalidModelResponse(f"{model} returned no choices (response {result.id})")
        calls = result.choices[0].message.tool_calls
        if calls is None or len(calls) != 1:
            raise InvalidModelResponse(f"{model} did not return exactly one output tool call (response {result.id})")
        tool_call, = calls
        function = tool_call.function
        if function.name != result_type.__name__:
            raise InvalidModelResponse(f"Unexpected output tool: {function.name}")
        try:
            parsed = result_type.model_validate_json(function.arguments)
        except ValidationError as error:
            raise InvalidModelResponse(f"{model} returned invalid {result_type.__name__} JSON or schema (response {result.id})") from error
        logger.info("[EXTRACTION] Extracted %s with %s", result_type.__name__, model)
        return parsed


@contextmanager
def create_extractor() -> Iterator[ExtractionManager]:
    with OpenAI(
        base_url="https://openrouter.ai/api/v1/",
        api_key=os.environ["OPENROUTER_API_KEY"],
        timeout=180,
        max_retries=0,
    ) as client:
        yield ExtractionManager(client)
