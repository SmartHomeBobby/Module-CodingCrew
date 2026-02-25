import logging
from typing import Any, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

logger = logging.getLogger(__name__)

class AskStakeholderInput(BaseModel):
    """Input parameters for the AskStakeholderTool."""
    question: str = Field(..., description="The highly specific question you need to ask the stakeholder.")
    context: str = Field(..., description="Any relevant context, code snippets, or alternative choices necessary for the stakeholder to make a decision.")

class AskStakeholderTool(BaseTool):
    """
    A Tool that allows the agent to pause execution and ask the human stakeholder a question via MQTT.
    """
    name: str = "AskStakeholderTool"
    description: str = (
        "Use this tool ONLY when you encounter a critical product decision, architectural choice, "
        "or missing requirement that prevents you from continuing your work. "
        "This tool will send a message to the stakeholder and block execution until they respond."
    )
    args_schema: Type[BaseModel] = AskStakeholderInput
    
    # We set these in initialization or inject them
    mqtt_handler: Any = None
    request_topic: str = "smarthomebobby/crewai/decision/request"
    timeout: int = 3600  # Default 1 hour timeout for human response

    def _run(self, question: str, context: str) -> str:
        if not self.mqtt_handler:
            return "Error: MQTT handler not configured for this tool."
            
        logger.info(f"Agent asking stakeholder via MQTT: {question}")
        response = self.mqtt_handler.ask_stakeholder(
            topic=self.request_topic,
            question=question,
            context=context,
            timeout=self.timeout
        )
        return f"Stakeholder answered: {response}"
