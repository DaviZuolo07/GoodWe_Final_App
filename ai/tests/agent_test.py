from ai.agents.chargeops_agent import ChargeOpsAgent


agent = ChargeOpsAgent()

print(
    agent.ask(
        "O que é carregamento AC?"
    )
)

print("\n" + "=" * 50 + "\n")

print(
    agent.ask(
        "E quais as vantagens dele?"
    )
)