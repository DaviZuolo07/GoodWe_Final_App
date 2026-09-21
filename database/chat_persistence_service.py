from database.repositories.user_repository import UserRepository
from database.repositories.chat_repository import ChatRepository
from database.repositories.message_repository import MessageRepository


class ChatPersistenceService:
    """
    Camada de serviço responsável por
    orquestrar persistência de usuários,
    conversas e mensagens.
    """

    def __init__(self):

        self.users = UserRepository()
        self.chats = ChatRepository()
        self.messages = MessageRepository()

    # ==================================================
    # USERS
    # ==================================================

    def create_user_if_not_exists(
        self,
        profile: dict
    ) -> int:
        """
        Busca usuário pelo nome.

        Caso não exista,
        cria no banco.
        """

        user = self.users.find_by_name(
            profile["name"]
        )

        if user:
            return user["id"]

        return self.users.create_user(
            profile
        )

    # ==================================================
    # CHATS
    # ==================================================

    def create_chat(
        self,
        user_id: int,
        title: str = "Nova Conversa"
    ) -> int:

        return self.chats.create_chat(
            user_id=user_id,
            title=title
        )

    def get_chat(
        self,
        chat_id: int
    ):

        return self.chats.get_chat_by_id(
            chat_id
        )

    def get_user_chats(
        self,
        user_id: int
    ):

        return self.chats.get_chats_by_user(
            user_id
        )
    
    # ==================================================
    # MESSAGES
    # ==================================================

    def save_user_message(
        self,
        chat_id: int,
        content: str
    ):

        self.messages.create_message(
            chat_id=chat_id,
            role="user",
            content=content
        )

    def save_assistant_message(
        self,
        chat_id: int,
        content: str
    ):

        self.messages.create_message(
            chat_id=chat_id,
            role="assistant",
            content=content
        )

    def load_chat_history(
        self,
        chat_id: int
    ):

        return self.messages.build_chat_history(
            chat_id
        )