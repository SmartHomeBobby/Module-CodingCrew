import logging
from typing import Any, List, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration

logger = logging.getLogger(__name__)

class MQTTLLM(BaseChatModel):
    """
    Custom LangChain Chat Model wrapper that routes requests to an MQTT topic
    and waits for a response from the `localLLMAgentModule`.
    """
    mqtt_handler: Any
    request_topic: str
    request_type: int = 0
    priority: int = 2
    timeout: int = 300
    stop: Optional[List[str]] = None
    
    @property
    def _llm_type(self) -> str:
        return "mqtt_chat_model"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        if stop is not None and len(stop) > 0:
            logger.warning("Stop sequences are not currently supported by MQTTLLM. They will be ignored.")
            
        # Compile messages into a single prompt string for the custom LLM Module
        prompt = "\n".join([f"{msg.type.capitalize()}: {msg.content}" for msg in messages])
            
        logger.debug(f"Sending prompt to LLM via MQTT: {prompt[:100]}...")
        response = self.mqtt_handler.ask_llm(
            topic=self.request_topic,
            request_text=prompt,
            request_type=self.request_type,
            priority=self.priority,
            timeout=self.timeout
        )
        
        generation = ChatGeneration(message=AIMessage(content=response))
        return ChatResult(generations=[generation])

    # CrewAI 0.100+ native custom LLM requirements:
    def call(self, messages: List[Any], callbacks: List[Any] = [], **kwargs: Any) -> str:
        """Fallback method called directly by some internal CrewAI utilities."""
        # Convert dictionaries or raw strings to BaseMessage format expected by _generate
        formatted_messages = []
        for msg in messages:
            if hasattr(msg, "content"):
                formatted_messages.append(msg)
            elif isinstance(msg, dict) and "content" in msg:
                role = msg.get("role", "user")
                formatted_messages.append(AIMessage(content=msg["content"]))
            elif isinstance(msg, str):
                formatted_messages.append(AIMessage(content=msg))
                
        result = self._generate(messages=formatted_messages, **kwargs)
        return result.generations[0].message.content
        
    def supports_stop_words(self) -> bool:
        return False
