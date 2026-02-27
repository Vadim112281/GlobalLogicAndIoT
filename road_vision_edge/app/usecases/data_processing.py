from app.entities.agent_data import AgentData
from app.entities.processed_agent_data import ProcessedAgentData


def process_agent_data(agent_data: AgentData) -> ProcessedAgentData:
    """
    Process agent data and classify the state of the road surface.
    Parameters:
        agent_data (AgentData): Agent data that contains accelerometer, GPS, and timestamp.
    Returns:
        processed_data (ProcessedAgentData): Processed data containing the classified state of
        the road surface and agent data.
    """
    z_value = agent_data.accelerometer.z

    if z_value > 11.0 or z_value < 5.0:
        road_state = "pothole"
    else:
        road_state = "normal"

    return ProcessedAgentData(road_state=road_state, agent_data=agent_data)
