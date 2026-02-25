import logging
import subprocess
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

logger = logging.getLogger(__name__)

class CommandExecutionInput(BaseModel):
    """Input parameters for the CommandExecutionTool."""
    command: str = Field(..., description="The shell command to execute (e.g. `dotnet build`, `flutter test`, `python script.py`).")
    cwd: str = Field(None, description="The working directory where the command should be run.")

class CommandExecutionTool(BaseTool):
    """
    A Tool that allows the agent to execute shell commands locally inside the Docker container.
    """
    name: str = "CommandExecutionTool"
    description: str = (
        "Use this tool to compile code, run tests, or execute scripts on your local system to verify "
        "your work before committing to GitHub. You have access to `dotnet` and `flutter` commands."
    )
    args_schema: Type[BaseModel] = CommandExecutionInput

    def _run(self, command: str, cwd: str = None) -> str:
        logger.info(f"Agent executing command: {command} in {cwd or 'current directory'}")
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300 # 5 min timeout
            )
            output = f"Return Code: {result.returncode}\n"
            if result.stdout:
                output += f"STDOUT:\n{result.stdout}\n"
            if result.stderr:
                output += f"STDERR:\n{result.stderr}\n"
                
            return output
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after 300 seconds."
        except Exception as e:
            return f"Error executing command: {e}"
