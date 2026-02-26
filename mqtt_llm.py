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
    timeout: int = 3600
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
        import time
        # Compile messages into a single prompt string for the custom LLM Module
        prompt = "\n".join(
            [f"{msg.type.capitalize()}: {msg.content}" for msg in messages])

        start_time = time.time()
        logger.info(f"Sending prompt to LLM via MQTT at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}...")
        response = self.mqtt_handler.ask_llm(
            topic=self.request_topic,
            request_text=prompt,
            request_type=self.request_type,
            priority=self.priority,
            timeout=self.timeout
        )
        duration = time.time() - start_time
        logger.info(f"LLM response received. Took {duration:.2f} seconds.")

        # Manually enforce stop words since MQTT payload doesn't support them natively
        if stop is not None and len(stop) > 0 and response:
            first_stop_idx = len(response)
            for stop_word in stop:
                idx = response.find(stop_word)
                if idx != -1 and idx < first_stop_idx:
                    first_stop_idx = idx
            if first_stop_idx < len(response):
                logger.debug(
                    f"Truncated response from len {len(response)} to {first_stop_idx} due to stop word")
                response = response[:first_stop_idx]

        # Fix hallucinated "Repaired JSON: " and JSON arrays 
        import re
        import json
        
        # 1. Remove "Repaired JSON:" prefix explicitly if it exists anywhere
        response = response.replace("Repaired JSON:", "").strip()
        
        # 2. Check if the response contains Action Input: [...]
        # The agent sometimes generates multiple list elements instead of one dict.
        pattern = r"(Action Input:\s*)(\[.*?\])\s*(?=\n|$)"
        match = re.search(pattern, response, flags=re.DOTALL)
        if match:
            prefix = match.group(1)
            json_array_str = match.group(2)
            try:
                arr = json.loads(json_array_str)
                if isinstance(arr, list) and len(arr) > 0 and isinstance(arr[0], dict):
                    first_obj_str = json.dumps(arr[0])
                    response = response[:match.start()] + prefix + first_obj_str + response[match.end():]
            except json.JSONDecodeError:
                pass
                
        # 3. Check if the entire response is just a JSON array (e.g. function calling hallucination)
        response = response.strip()
        if response.startswith("[") and response.endswith("]"):
            try:
                arr = json.loads(response)
                if isinstance(arr, list) and len(arr) > 0 and isinstance(arr[0], dict):
                    response = json.dumps(arr[0])
            except json.JSONDecodeError:
                pass

        if not response:
            response = "Error: Invalid or empty response from MQTT LLM layer."

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
        if not result or not result.generations or not result.generations[0].message.content:
            return "Error: Empty or invalid fallback generation."
        return result.generations[0].message.content

    def supports_stop_words(self) -> bool:
        return True
