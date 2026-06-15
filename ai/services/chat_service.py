from ai.agents.chargeops_agent import ChargeOpsAgent


class ChatService:

    def __init__(
        self,
        system_context: str = "",
        user_context: str = ""
    ):

        self.agent = ChargeOpsAgent(
            system_context=system_context,
            user_context=user_context
        )

    def send_message(
        self,
        user_message: str
    ) -> str:

        return self.agent.ask(
            user_message
        )

    def clear_chat(self):

        self.agent.clear_memory()