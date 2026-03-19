from app.entities.agent_data import AgentData
from app.entities.processed_agent_data import ProcessedAgentData
from app.entities.processed_agent_data import Dimensions


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

    pothole_detected = z_value > 11.0 or z_value < 5.0
    if pothole_detected:
        road_state = "pothole"
    else:
        road_state = "normal"

    # We don't have real pothole geometry in sensor data.
    # For demo purposes we derive a plausible "depth" from accelerometer z.
    if pothole_detected:
        derived_depth = abs(z_value - 9.0) + 1.0
        # Ensure depth>5 for pothole to show difficulty coefficient behavior in UI.
        depth = max(6.0, min(10.0, derived_depth))
    else:
        depth = 3.0

    dimensions = Dimensions(length=20.0, width=20.0, depth=float(depth))
    return ProcessedAgentData(road_state=road_state, agent_data=agent_data, dimensions=dimensions)
