import json
import logging
import threading
import time
import uuid
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

class MQTTHandler:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(MQTTHandler, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(
        self,
        broker="127.0.0.1",
        port=1883,
        user="",
        password="",
        llm_response_topic="smarthomebobby/llm/response",
        decision_response_topic="smarthomebobby/crewai/decision/response"
    ):
        if self._initialized:
            return
            
        self.broker = broker
        self.port = port
        self.user = user
        self.password = password
        
        self.llm_response_topic = llm_response_topic
        self.decision_response_topic = decision_response_topic
        
        # Maps trace_id -> {"event": threading.Event(), "response": dict}
        self.pending_requests = {}
        self.pending_decisions = {}
        
        self.client_id = f"crewai_agent_{uuid.uuid4().hex[:8]}"
        
        try:
            from paho.mqtt.client import CallbackAPIVersion
            self.client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=self.client_id, clean_session=True)
        except Exception:
            self.client = mqtt.Client(client_id=self.client_id, clean_session=True)
            
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        if self.user and self.password:
            self.client.username_pw_set(self.user, self.password)
            
        self._initialized = True

    def start(self):
        logger.info(f"Connecting to MQTT broker at {self.broker}:{self.port}...")
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info("Connected to MQTT Broker successfully.")
            client.subscribe(self.llm_response_topic, qos=2)
            client.subscribe(self.decision_response_topic, qos=2)
        else:
            logger.error(f"Failed to connect, return code {rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            
            if msg.topic == self.llm_response_topic:
                trace_id = payload.get("TraceId", payload.get("traceId"))
                if trace_id and trace_id in self.pending_requests:
                    req = self.pending_requests[trace_id]
                    req["response"] = payload
                    req["event"].set()
                    
            elif msg.topic == self.decision_response_topic:
                event_id = payload.get("EventId", payload.get("eventId"))
                if event_id and event_id in self.pending_decisions:
                    dec = self.pending_decisions[event_id]
                    dec["response"] = payload
                    dec["event"].set()
                    
        except Exception as e:
            logger.error(f"Error parsing incoming message on {msg.topic}: {e}")

    def ask_llm(self, topic: str, request_text: str, request_type: int = 0, priority: int = 2, timeout: int = 300) -> str:
        trace_id = str(uuid.uuid4())
        event_id = str(uuid.uuid4())
        
        payload = {
            "TraceId": trace_id,
            "EventId": event_id,
            "CreationTime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "Sender": {"Module": "crewai", "Host": self.client_id, "Version": "1.0.0"},
            "Priority": priority,
            "RequestType": request_type,
            "Request": request_text
        }
        
        event = threading.Event()
        self.pending_requests[trace_id] = {"event": event, "response": None}
        
        logger.debug(f"Publishing LLM request to {topic} with trace_id {trace_id}")
        self.client.publish(topic, json.dumps(payload), qos=2)
        
        completed = event.wait(timeout)
        
        try:
            if completed:
                resp = self.pending_requests[trace_id]["response"]
                return resp.get("Response", resp.get("response", ""))
            else:
                logger.error(f"LLM request timed out after {timeout}s")
                return "Error: LLM request timed out."
        finally:
            if trace_id in self.pending_requests:
                del self.pending_requests[trace_id]

    def ask_stakeholder(self, topic: str, question: str, context: str, timeout: int = 3600) -> str:
        trace_id = str(uuid.uuid4())
        event_id = str(uuid.uuid4())
        
        payload = {
            "TraceId": trace_id,
            "EventId": event_id,
            "CreationTime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "Sender": {"Module": "crewai-stakeholder-tool", "Host": self.client_id, "Version": "1.0.0"},
            "Priority": 2,
            "Question": question,
            "Context": context
        }
        
        event = threading.Event()
        self.pending_decisions[event_id] = {"event": event, "response": None}
        
        logger.info(f"Asking stakeholder: {question}")
        self.client.publish(topic, json.dumps(payload), qos=2)
        
        completed = event.wait(timeout)
        
        try:
            if completed:
                resp = self.pending_decisions[event_id]["response"]
                return resp.get("Answer", resp.get("answer", ""))
            else:
                logger.error(f"Stakeholder request timed out after {timeout}s")
                return "Error: Stakeholder response timed out."
        finally:
            if event_id in self.pending_decisions:
                del self.pending_decisions[event_id]
