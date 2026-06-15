from pathlib import Path
import sqlite3


# Diretório database/
DATABASE_DIR = Path(__file__).resolve().parent

# Arquivo físico do banco
DATABASE_FILE = DATABASE_DIR / "goodwe.db"


def get_connection():
    """
    Cria conexão SQLite.

    Retorna:
        sqlite3.Connection
    """

    connection = sqlite3.connect(DATABASE_FILE)

    # Permite acessar colunas por nome
    connection.row_factory = sqlite3.Row

    return connection