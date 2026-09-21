from pathlib import Path


class PromptLoader:
    """
    Responsável por carregar os arquivos de prompt.

    Nesta Sprint:
    - system_prompt.txt
    - few_shots.txt

    Futuramente:
    - prompts por persona
    - prompts especializados
    """

    BASE_PATH = Path("ai/prompts")

    @classmethod
    def load_system_prompt(cls) -> str:

        file_path = cls.BASE_PATH / "system_prompt.txt"

        return file_path.read_text(
            encoding="utf-8"
        )

    @classmethod
    def load_few_shots(cls) -> str:

        file_path = cls.BASE_PATH / "few_shots.txt"

        return file_path.read_text(
            encoding="utf-8"
        )