from ai.memory.conversation_memory import ConversationMemory
from ai.services.llm_provider import LLMProvider

from ai.prompts.prompt_loader import PromptLoader
from ai.context.goodwe_context import GOODWE_CONTEXT


class ChargeOpsAgent:

    def __init__(
        self,
        system_context: str = "",
        user_context: str = ""
    ):

        self.memory = ConversationMemory()

        self.provider = LLMProvider()

        self.system_prompt = (
            PromptLoader.load_system_prompt()
        )

        self.few_shots = (
            PromptLoader.load_few_shots()
        )

        self.system_context = system_context
        self.user_context = user_context

    def ask(self, user_message: str):

        messages = []

        messages.append(
            {
                "role": "system",
                "content": self.system_prompt
            }
        )

        messages.append(
            {
                "role": "system",
                "content": GOODWE_CONTEXT
            }
        )

        if self.system_context:

            messages.append(
                {
                    "role": "system",
                    "content": self.system_context
                }
            )

        if self.user_context:

            messages.append(
                {
                    "role": "system",
                    "content": self.user_context
                }
            )

        messages.append(
            {
                "role": "system",
                "content": self.few_shots
            }
        )

        messages.extend(
            self.memory.get_messages()
        )

        messages.append(
            {
                "role": "user",
                "content": user_message
            }
        )

        response = self.provider.generate_response(
            messages
        )

        self.memory.add_user_message(
            user_message
        )

        self.memory.add_assistant_message(
            response
        )

        return response

    def clear_memory(self):

        self.memory.clear()