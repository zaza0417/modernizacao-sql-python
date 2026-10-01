from modernizer.graph.state import PipelineState
from modernizer.llm import get_llm
from modernizer.llm.prompt import SYSTEM_PROMPT, build_user_prompt


def generate_node(state: PipelineState) -> dict:
    attempts = state.get("attempts", 0) + 1
    try:
        result = get_llm().generate(SYSTEM_PROMPT, build_user_prompt(state))
    except Exception as exc:
        return {
            "errors": [f"generate: {exc}"],
            "status": "falha",
            "attempts": attempts,
        }
    return {
        "generated_code": result["code"],
        "generation": {
            "decisions": result["decisions"],
            "model": result["model"],
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
        },
        "attempts": attempts,
    }