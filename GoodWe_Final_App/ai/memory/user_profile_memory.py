class UserProfileMemory:
    """
    Memória de perfil do usuário.

    Responsável por transformar os dados
    cadastrados no Streamlit em contexto
    para o LLM.
    """

    def __init__(self, profile: dict):

        self.profile = profile

    def build_context(self) -> str:

        return f"""
==================================================
USER PROFILE
==================================================

Nome: {self.profile.get("name", "")}

Persona: {self.profile.get("persona", "")}

Modelo do veículo:
{self.profile.get("car_model", "")}

Capacidade da bateria:
{self.profile.get("battery_kwh", "")} kWh

Potência preferencial do carregador:
{self.profile.get("charger_kw", "")} kW

Bloco:
{self.profile.get("block", "")}

Apartamento:
{self.profile.get("apartment", "")}

IMPORTANTE:

Esses dados pertencem ao usuário atual.

Considere essas informações como verdade.

Não solicite novamente esses dados.

Utilize automaticamente essas informações
em cálculos, estimativas e explicações.
"""