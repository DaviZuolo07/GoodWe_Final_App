from ai.services.llm_provider import LLMProvider

provider = LLMProvider()

response = provider.generate_response(
    [
        {
            "role": "user",
            "content": "O que é carregamento AC?"
        }
    ]
)

print(response)