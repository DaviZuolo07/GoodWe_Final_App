from database.connection import get_connection


class MessageRepository:
    """
    Responsável pelas operações
    da tabela messages.
    """

    @staticmethod
    def create_message(
        chat_id: int,
        role: str,
        content: str
    ) -> int:
        """
        Salva uma mensagem.

        role:
            user
            assistant

        Retorna:
            id da mensagem criada.
        """

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO messages (
                    chat_id,
                    role,
                    content
                )
                VALUES (?, ?, ?)
                """,
                (
                    chat_id,
                    role,
                    content
                )
            )

            conn.commit()

            return cursor.lastrowid

        finally:
            conn.close()

    @staticmethod
    def get_message_by_id(
        message_id: int
    ):

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM messages
                WHERE id = ?
                """,
                (message_id,)
            )

            return cursor.fetchone()

        finally:
            conn.close()

    @staticmethod
    def get_messages_by_chat(
        chat_id: int
    ):

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM messages
                WHERE chat_id = ?
                ORDER BY id ASC
                """,
                (chat_id,)
            )

            return cursor.fetchall()

        finally:
            conn.close()

    @staticmethod
    def build_chat_history(
        chat_id: int
    ):
        """
        Retorna histórico em formato
        compatível com o Streamlit atual.

        Exemplo:

        [
            {
                "role": "user",
                "content": "Olá"
            },
            {
                "role": "assistant",
                "content": "Oi"
            }
        ]
        """

        messages = MessageRepository.get_messages_by_chat(
            chat_id
        )

        history = []

        for msg in messages:

            history.append(
                {
                    "role": msg["role"],
                    "content": msg["content"]
                }
            )

        return history

    @staticmethod
    def delete_messages_by_chat(
        chat_id: int
    ):

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM messages
                WHERE chat_id = ?
                """,
                (chat_id,)
            )

            conn.commit()

        finally:
            conn.close()

    @staticmethod
    def count_messages(
        chat_id: int
    ) -> int:

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM messages
                WHERE chat_id = ?
                """,
                (chat_id,)
            )

            result = cursor.fetchone()

            return result[0]

        finally:
            conn.close()