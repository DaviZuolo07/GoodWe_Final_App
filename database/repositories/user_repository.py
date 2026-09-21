from database.connection import get_connection


class UserRepository:
    """
    Responsável pelas operações
    da tabela users.
    """

    @staticmethod
    def create_user(profile: dict) -> int:
        """
        Cria um usuário.

        Retorna:
            id do usuário criado.
        """

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO users (
                    name,
                    persona,
                    car_model,
                    battery_kwh,
                    charger_kw,
                    block,
                    apartment
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.get("name"),
                    profile.get("persona"),
                    profile.get("car_model"),
                    profile.get("battery_kwh"),
                    profile.get("charger_kw"),
                    profile.get("block"),
                    profile.get("apartment")
                )
            )

            conn.commit()

            return cursor.lastrowid

        finally:
            conn.close()

    @staticmethod
    def find_by_name(name: str):
        """
        Busca usuário pelo nome.
        """

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM users
                WHERE name = ?
                """,
                (name,)
            )

            return cursor.fetchone()

        finally:
            conn.close()

    @staticmethod
    def get_user_by_id(user_id: int):

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM users
                WHERE id = ?
                """,
                (user_id,)
            )

            return cursor.fetchone()

        finally:
            conn.close()

    @staticmethod
    def get_all_users():

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM users
                ORDER BY id DESC
                """
            )

            return cursor.fetchall()

        finally:
            conn.close()
