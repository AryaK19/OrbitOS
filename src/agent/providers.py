"""
LLM provider factory for OrbitOS.
Maps provider/model-name strings to LangChain chat model instances.
"""

from langchain_core.language_models import BaseChatModel

from ..utils.logger import get_logger

logger = get_logger()

# Models available via direct API calls.
# Format: (model_id, display_name)
# model_id = "provider/model-name"
AVAILABLE_MODELS = [
    # Google Gemini
    ("google/gemini-2.5-flash", "Gemini 2.5 Flash"),
    ("google/gemini-2.5-pro", "Gemini 2.5 Pro"),
    ("google/gemini-2.0-flash", "Gemini 2.0 Flash"),
    ("google/gemini-3-flash-preview", "Gemini 3 Flash Preview"),
    ("google/gemini-3.1-flash-lite-preview", "Gemini 3.1 Flash Lite Preview"),
    ("google/gemini-3.1-pro-preview", "Gemini 3.1 Pro Preview"),

    # OpenAI
    ("openai/gpt-4o", "GPT-4o"),
    ("openai/gpt-4o-mini", "GPT-4o Mini"),
    ("openai/gpt-4.1-mini", "GPT-4.1 Mini"),
    ("openai/gpt-4.1-nano", "GPT-4.1 Nano"),
]


def create_llm(
    model_id: str,
    temperature: float = 0.1,
    timeout: int = 120,
) -> BaseChatModel:
    """Create a LangChain chat model from a provider/model-name string.

    Args:
        model_id: Format "provider/model-name" (e.g. "google/gemini-2.5-flash").
        temperature: Sampling temperature.
        timeout: Request timeout in seconds.

    Returns:
        A BaseChatModel instance ready for use with LangGraph.
    """
    if "/" not in model_id:
        raise ValueError(
            f"Invalid model_id '{model_id}'. Expected format: provider/model-name"
        )

    provider, model_name = model_id.split("/", 1)

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            timeout=timeout,
        )
    elif provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError(
                "langchain-openai is not installed. Run: uv add langchain-openai"
            )
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            timeout=timeout,
        )
    elif provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise ImportError(
                "langchain-anthropic is not installed. Run: uv add langchain-anthropic"
            )
        return ChatAnthropic(
            model=model_name,
            temperature=temperature,
            timeout=timeout,
        )
    else:
        raise ValueError(
            f"Unknown provider '{provider}'. Supported: google, openai, anthropic"
        )
