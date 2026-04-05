"""Configuration for models that don't support tool calling."""

NO_TOOL_MODELS = {
    "gemma3:1b",
    "gemma3:4b",
    "qwen3.5:0.8B",
    "llama3.2:1b",
    "phi3:mini",
}


def should_disable_tools(model: str) -> bool:
    """Check if model supports tool calling."""
    model_lower = model.lower()
    return any(no_tool in model_lower for no_tool in NO_TOOL_MODELS)
