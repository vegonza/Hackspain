import os
import base64
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any, TypeVar, cast

from openai import OpenAI
from openai.types.chat import ChatCompletionContentPartParam
from pydantic import BaseModel
from shared.logger import get_logger
from shared.usage import UsageEntry, UsageRecord

MODEL = "openai/gpt-5.6-luna"
PROMPTS_DIRECTORY = Path(__file__).parent / "prompts"
Result = TypeVar("Result", bound=BaseModel)
logger = get_logger()


def load_prompt(filename: str) -> str:
    return (PROMPTS_DIRECTORY / filename).read_text(encoding="utf-8").strip()


class ExtractionManager:
    def __init__(self, client: OpenAI) -> None:
        self.client = client

    def run(
        self, instruction: str, content: str, result_type: type[Result],
        usage: UsageRecord | None = None,
        page_images: Sequence[bytes] = (),
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
            model=MODEL,
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
                    "parameters": result_type.model_json_schema(),
                },
            }],
            tool_choice="required",
            parallel_tool_calls=False,
            extra_body={"usage": {"include": True}},
        )
        if usage is not None:
            reported_usage = result.usage.model_dump()
            provider = cast(dict[str, Any], result.model_extra)["provider"]
            usage.provider = provider
            usage.usage.append(UsageEntry(
                model=result.model, provider=provider,
                cost=Decimal(str(reported_usage["cost"])),
                details={"response_id": result.id, "result_type": result_type.__name__, **reported_usage},
            ))
        tool_call, = result.choices[0].message.tool_calls
        function = tool_call.function
        if function.name != result_type.__name__:
            raise ValueError(f"Unexpected output tool: {function.name}")
        parsed = result_type.model_validate_json(function.arguments)
        logger.info("[EXTRACTION] Extracted %s with %s", result_type.__name__, MODEL)
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
