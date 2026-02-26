import os
import sys
import logging
from dotenv import load_dotenv

from mqtt_handler import MQTTHandler
from crew_setup import create_coding_crew

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def main():
    load_dotenv()
    
    # 1. Environment Config
    mqtt_broker = os.getenv("MQTT_BROKER", "tower")
    mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
    mqtt_user = os.getenv("MQTT_USER", "")
    mqtt_password = os.getenv("MQTT_PASSWORD", "")
    
    request_topic = os.getenv("MQTT_TOPIC_REQUEST", "smarthomebobby/llm/request")
    response_topic = os.getenv("MQTT_TOPIC_RESPONSE", "smarthomebobby/llm/response")
    decision_request_topic = os.getenv("MQTT_TOPIC_DECISION_REQUEST", "smarthomebobby/crewai/decision/request")
    decision_response_topic = os.getenv("MQTT_TOPIC_DECISION_RESPONSE", "smarthomebobby/crewai/decision/response")
    
    project_goal = os.getenv("PROJECT_GOAL", "program an app for tracking chores for couples")
    technical_details = os.getenv("TECHNICAL_DETAILS", "Follow general best practices.")
    
    logger.info("Starting localCodingCrewModule...")
    
    # Ensure agent file outputs land in the mounted volume instead of the /app script root
    output_dir = "/app/generated_projects"
    os.makedirs(output_dir, exist_ok=True)
    if os.getcwd() not in sys.path:
        sys.path.append(os.getcwd())
    os.chdir(output_dir)
    logger.info(f"Changed working directory to {output_dir}")
    
    # 2. Init and Start MQTT Handler Thread
    mqtt = MQTTHandler(
        broker=mqtt_broker,
        port=mqtt_port,
        user=mqtt_user,
        password=mqtt_password,
        llm_response_topic=response_topic,
        decision_response_topic=decision_response_topic
    )
    mqtt.start()
    
    try:
        # 3. Initialize the Crew
        logger.info(f"Initializing Crew with goal: {project_goal}")
        crew = create_coding_crew(
            project_goal=project_goal,
            technical_details=technical_details,
            request_topic=request_topic,
            decision_request_topic=decision_request_topic
        )
        
        # 4. Run the Crew AI Loop
        logger.info("Kicking off the CrewAI execution...")
        result = crew.kickoff()
        
        logger.info("CrewAI execution finished successfully:")
        logger.info(result)
        
    except KeyboardInterrupt:
        logger.info("Interrupted. Shutting down...")
    except Exception as e:
        logger.error(f"Error during CrewAI execution: {e}")
    finally:
        mqtt.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()
