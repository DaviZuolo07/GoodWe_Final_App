from ai.memory.conversation_memory import ConversationMemory


memory = ConversationMemory()

memory.add_user_message(
    "Qual carregador está disponível?"
)

memory.add_assistant_message(
    "O carregador AC-01 está disponível."
)

print(memory.get_messages())