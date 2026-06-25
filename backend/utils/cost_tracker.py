from sqlalchemy.ext.asyncio import AsyncSession
from models import RunCost
from datetime import datetime

async def log_cost(db: AsyncSession, run_id: str, agent_name: str, input_tokens: int, output_tokens: int, total_cost: float):
    cost_entry = RunCost(
        run_id=run_id,
        agent_name=agent_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_cost=total_cost
    )
    db.add(cost_entry)
    await db.commit()
