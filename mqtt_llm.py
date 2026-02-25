import logging
from typing import Any, List, Optional
from langchain_core.language_models.llms import LLM

logger = logging.getLogger(__name__)

class MQTTLLM(LLM):
    """
    Custom LangChain LLM wrapper that routes requests to an MQTT topic
    and waits for a response from the `localLLMAgentModule`.
    """
    mqtt_handler: Any
    request_topic: str
    request_type: int = 0
    priority: int = 2
    timeout: int = 300
    
    @property
    def _llm_type(self) -> str:
        return "mqtt_llm"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> str:
        if stop is not None and len(stop) > 0:
            logger.warning("Stop sequences are not currently supported by MQTTLLM. They will be ignored.")
            
        logger.debug(f"Sending prompt to LLM via MQTT: {prompt[:100]}...")
        response = self.mqtt_handler.ask_llm(
            topic=self.request_topic,
            request_text=prompt,
            request_type=self.request_type,
            priority=self.priority,
            timeout=self.timeout
        )
        return response
