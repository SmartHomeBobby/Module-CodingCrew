import os
import logging
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

logger = logging.getLogger(__name__)

class CreateGithubRepoInput(BaseModel):
    """Input parameters for the CreateGithubRepoTool."""
    repo_name: str = Field(..., description="The name of the new GitHub repository to create (e.g. 'couple-chores-app').")
    description: str = Field(..., description="A short description of the repository.")

class CreateGithubRepoTool(BaseTool):
    """
    A Tool that allows the agent to create a new remote GitHub repository, 
    initialize it locally, and link them.
    This requires the GITHUB_TOKEN environment variable to be set.
    """
    name: str = "CreateGithubRepoTool"
    description: str = (
        "Use this tool to create a brand new GitHub repository under your authenticated account. "
        "The repository will ALWAYS be created as PRIVATE to protect the stakeholder's code and privacy. "
        "It will also initialize a local git repository in the current working directory, "
        "commit an initial README, and push it to the remote main branch. "
    )
    args_schema: Type[BaseModel] = CreateGithubRepoInput

    def _run(self, repo_name: str, description: str) -> str:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            return "Error: GITHUB_TOKEN environment variable is not set. Ask the stakeholder to provide it or set it in docker-compose.override.yml."
            
        try:
            from github import Github
            from github import Auth
            
            auth = Auth.Token(token)
            g = Github(auth=auth)
            user = g.get_user()
            
            # Create remote repo
            logger.info(f"Creating GitHub repository: {repo_name}")
            repo = user.create_repo(
                name=repo_name,
                description=description,
                private=True,
                auto_init=True
            )
            clone_url = repo.clone_url
            
            # Since the user might have a generic github setup, let's inject the token into the clone URL for git operations
            auth_url = clone_url.replace("https://", f"https://{token}@")
            
            import subprocess
            
            # Clone it locally
            logger.info(f"Cloning {clone_url} locally...")
            subprocess.run(f"git clone {auth_url} .", shell=True, check=True)
            
            return f"Successfully created GitHub repository '{repo_name}' and cloned it locally. Remote URL: {clone_url}"
            
        except Exception as e:
            logger.error(f"Error creating GitHub repository: {e}")
            return f"Error creating repository: {e}"
