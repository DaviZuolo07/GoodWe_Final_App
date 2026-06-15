from pathlib import Path

from database.connection import get_connection


def initialize_database():
    """
    Cria todas as tabelas do sistema
    a partir do schema.sql.
    """

    schema_path = (
        Path(__file__)
        .resolve()
        .parent
        / "schema.sql"
    )

    with open(
        schema_path,
        "r",
        encoding="utf-8"
    ) as file:

        schema = file.read()

    conn = get_connection()

    try:
        conn.executescript(schema)
        conn.commit()

        print(
            "Banco criado com sucesso."
        )

    except Exception as error:

        print(
            f"Erro ao criar banco: {error}"
        )

    finally:
        conn.close()


if __name__ == "__main__":
    initialize_database()