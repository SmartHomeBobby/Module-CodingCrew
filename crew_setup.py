import logging
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool

from mqtt_handler import MQTTHandler
from mqtt_llm import MQTTLLM
from command_tool import CommandExecutionTool

logger = logging.getLogger(__name__)

def create_coding_crew(
    project_goal: str,
    technical_details: str,
    request_topic: str,
    decision_request_topic: str
) -> Crew:
    """
    Creates and returns a Crew configured to work on the given project goal.
    """
    # 1. Initialize the MQTT Handler
    mqtt = MQTTHandler()
    
    # 2. Setup the custom LLMs pointing to the local MQTT topic
    # We might use different types or priorities if our localLLMAgentModule supports them.
    # Type 1 = CodeGeneration typically based on the module setup.
    llm_planner = MQTTLLM(mqtt_handler=mqtt, request_topic=request_topic, request_type=0, priority=1)
    llm_coder = MQTTLLM(mqtt_handler=mqtt, request_topic=request_topic, request_type=1, priority=1)
    
    # 3. Setup the tools
    execution_tool = CommandExecutionTool()
    
    # --- CREWAI 0.100+ CUSTOM LLM HOTFIX ---
    # Newer versions of CrewAI aggressively intercept custom LangChain objects and try to coerce 
    # them into LiteLLM wrappers (which crashes looking for OpenAI keys). 
    # We monkey-patch the internal factory to skip validation and accept our MQTTLLM natively.
    def bypass_llm(llms, **kwargs): return llms
    import crewai.agent.core
    crewai.agent.core.create_llm = bypass_llm
    # ---------------------------------------
    
    from github_tools import CreateGithubRepoTool
    github_tool = CreateGithubRepoTool()
    
    @tool("GitCommitPushTool")
    def git_commit_push(message: str) -> str:
        """Commits all local changes and pushes them to the remote GitHub repository."""
        # For this prototype we just use the execution tool to run git commands
        from command_tool import CommandExecutionTool
        executor = CommandExecutionTool()
        executor._run("git config --global user.email 'crewai@smarthomebobby.local'")
        executor._run("git config --global user.name 'CrewAI Agent'")
        executor._run("git add .")
        executor._run(f'git commit -m "{message}"')
        return executor._run("git push")

    dev_tools = [execution_tool]
    git_tools = [execution_tool, github_tool, git_commit_push]

    # 4. Define Agents
    product_owner = Agent(
        role="Product Owner",
        goal="Define the product features and answer any possible questions about feature details of the app being built.",
        backstory="You are the Product Owner. You have the canonical vision for the application. When developers or architects "
                  "are unsure about a feature requirement, user flow, or product detail, they ask you and you decide what to do. "
                  "You never write code, you only clarify product requirements.",
        allow_delegation=False,
        verbose=True,
        llm=llm_planner,
        tools=[]
    )
    
    software_architect = Agent(
        role="Senior Software Architect",
        goal="Design the architecture and project structure for the app based on requirements.",
        backstory="You are an expert system architect specializing in Flutter and C# .NET backends. "
                  "You decide the directory structures, frameworks, and patterns to build highly scalable systems.",
        allow_delegation=True,
        verbose=True,
        llm=llm_planner,
        tools=[]
    )
    
    senior_developer = Agent(
        role="Senior Full-Stack Developer",
        goal="Write robust code in Flutter and C# .NET to implement the architecture.",
        backstory="You are a seasoned developer. You write tests, you verify your code dynamically by building "
                  "it locally, and only when the local builds pass do you commit code.",
        allow_delegation=False,
        verbose=True,
        llm=llm_coder,
        tools=dev_tools
    )

    quality_assurance = Agent(
        role="QA Engineer",
        goal="Ensure all requirements are met and code compiles flawlessly.",
        backstory="You are obsessed with quality. You build the project using standard dotnet and flutter tools, "
                  "and push it back to the developer if it fails. You verify code locally.",
        allow_delegation=True,
        verbose=True,
        llm=llm_planner,
        tools=dev_tools
    )
    
    data_privacy_officer = Agent(
        role="Data Privacy Officer",
        goal="Enforce the 'need-to-know' principle and audit code for secrets before deployment.",
        backstory="You are a strict Data Privacy Officer. You review architecture to ensure only strictly necessary "
                  "data is collected. Before any code is committed, you aggressively scan the codebase to ensure "
                  "no tokens, API keys, or excessive telemetry are hardcoded or tracked. You are the ONLY agent allowed to push code.",
        allow_delegation=True,
        verbose=True,
        llm=llm_planner,
        tools=git_tools
    )

    # 5. Define Tasks
    planning_task = Task(
        description=f"Analyze the project goal: '{project_goal}'. Consider all these technical details: '{technical_details}'. "
                    "Decide on the tech stack (e.g. Flutter frontend, C# backend), database storage strategy, and API contracts. "
                    "Collaborate tightly with the Privacy Officer to establish a 'Need-to-Know' data handling policy from the start. "
                    "Ask the Product Owner for clarification on any missing product requirements regarding user onboarding or features.",
        expected_output="A detailed architecture markdown document along with a clear setup script blueprint that respects privacy.",
        agent=software_architect
    )

    coding_task = Task(
        description="Implement the architecture. First, initialize the git repository and project skeletons via local commands. "
                    "Then implement the core features as defined by the architect. Use your execution tool to BUILD and TEST "
                    "the code constantly.",
        expected_output="A fully built and compiling codebase with initial unit tests passing.",
        agent=senior_developer
    )

    qa_task = Task(
        description="Run local compilation commands on the source code generated by the developer. E.g. `dotnet build`, "
                    "`flutter test` (or test equivalents). If errors occur, document them or send back. Do NOT push to GitHub.",
        expected_output="Confirmation of valid build and functional baseline.",
        agent=quality_assurance
    )
    
    privacy_audit_task = Task(
        description="Aggressively audit the generated architecture and codebase using local terminal commands (like 'grep' or 'find') "
                    "to ensure no sensitive tokens, API keys, or unnecessary user data fields are mapped. Enforce the "
                    "'need-to-know' principle. Check every single code change. ONLY IF the codebase is clean and secure, use your Git tools to "
                    "create the remote repository and commit/push the final codebase to GitHub. If it violates privacy, fix it first.",
        expected_output="Confirmation of a clean privacy audit and a successful GitHub push.",
        agent=data_privacy_officer
    )

    # 6. Assemble the Crew
    crew = Crew(
        agents=[product_owner, software_architect, senior_developer, quality_assurance, data_privacy_officer],
        tasks=[planning_task, coding_task, qa_task, privacy_audit_task],
        process=Process.sequential,
        verbose=True
    )

    return crew
