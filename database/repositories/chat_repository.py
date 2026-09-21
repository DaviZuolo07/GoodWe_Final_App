from database.connection import get_connection


class ChatRepository:
    """
    Responsável pelas operações
    da tabela chats.
    """

    @staticmethod
    def create_chat(
        user_id: int,
        title: str = None
    ) -> int:
        """
        Cria uma nova conversa.

        Retorna:
            id da conversa criada.
        """

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO chats (
                    user_id,
                    title
                )
                VALUES (?, ?)
                """,
                (
                    user_id,
                    title
                )
            )

            conn.commit()

            return cursor.lastrowid

        finally:
            conn.close()

    @staticmethod
    def get_chat_by_id(
        chat_id: int
    ):

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM chats
                WHERE id = ?
                """,
                (chat_id,)
            )

            return cursor.fetchone()

        finally:
            conn.close()

    @staticmethod
    def get_chats_by_user(
        user_id: int
    ):

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM chats
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (user_id,)
            )

            return cursor.fetchall()

        finally:
            conn.close()

    @staticmethod
    def update_title(
        chat_id: int,
        title: str
    ):

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE chats
                SET title = ?
                WHERE id = ?
                """,
                (
                    title,
                    chat_id
                )
            )

            conn.commit()

        finally:
            conn.close()

    @staticmethod
    def delete_chat(
        chat_id: int
    ):

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM chats
                WHERE id = ?
                """,
                (chat_id,)
            )

            conn.commit()

        finally:
            conn.close()
