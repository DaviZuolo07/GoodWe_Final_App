class ConversationMemory:
    """
    Memória conversacional da sessão.

    Responsável por armazenar o histórico completo
    da conversa durante a execução do chatbot.

    Nesta Sprint:
    - memória em RAM
    - uma sessão

    Futuramente:
    - persistência em banco
    - múltiplos usuários
    - múltiplas sessões
    """

    def __init__(self):

        self.messages = []

    def add_user_message(self, content: str):

        self.messages.append(
            {
                "role": "user",
                "content": content
            }
        )

    def add_assistant_message(self, content: str):

        self.messages.append(
            {
                "role": "assistant",
                "content": content
            }
        )

    def get_messages(self):

        return self.messages.copy()

    def clear(self):

        self.messages.clear()

    def has_history(self):

        return len(self.messages) > 0