import os

from langchain.chat_models import init_chat_model

from graph.state import ReviewState

# Maps our provider input to LangChain's model_provider string
PROVIDER_MAP = {
    "anthropic": "anthropic",
    "openai": "openai",
    "google_genai": "google_genai",
}

# Each provider's LangChain integration reads its key from a different env var
PROVIDER_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google_genai": "GOOGLE_API_KEY",
}

# Small per-provider prompt adjustments to normalize output style/verbosity
PROVIDER_PROMPT_SUFFIX = {
    "openai": "\n\nRespond in concise bullet points only.",
    "google_genai": "\n\nBe direct — skip preamble and disclaimers.",
    "anthropic": "",
}


def build_model():
    provider = PROVIDER_MAP[os.environ["MODEL_PROVIDER"]]
    model_name = os.environ["MODEL_NAME"]
    api_key = os.environ["API_KEY"]

    key_env = PROVIDER_KEY_ENV[provider]
    os.environ[key_env] = api_key

    return init_chat_model(model_name, model_provider=provider)


def review_node(state: ReviewState) -> ReviewState:
    model = build_model()
    provider = PROVIDER_MAP[os.environ["MODEL_PROVIDER"]]
    suffix = PROVIDER_PROMPT_SUFFIX.get(provider, "")

    full_prompt = (
        f"{state['prompt']}{suffix}\n\n"
        f"PR context:\n{state['context']}\n\n"
        f"Here is the diff:\n{state['diff']}"
    )
    response = model.invoke(full_prompt)

    return {**state, "result": response.content}
