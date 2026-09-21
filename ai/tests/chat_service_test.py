from ai.services.chat_service import ChatService


chat = ChatService()

print(
    chat.send_message(
        "O que é um carregador AC?"
    )
)

print("\n")

print(
    chat.send_message(
        "Quais as vantagens dele?"
    )
)