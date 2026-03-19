from pydantic import BaseModel
from app.entities.agent_data import AgentData


class Dimensions(BaseModel):
    """
    Dimensions of a pothole (cm).
    Used for economic estimation of repair cost.
    """

    length: float
    width: float
    depth: float


class ProcessedAgentData(BaseModel):
    road_state: str
    agent_data: AgentData
    dimensions: Dimensions
