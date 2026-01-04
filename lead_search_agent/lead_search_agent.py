from agency_swarm import Agent, ModelSettings
from agency_swarm.tools import WebSearchTool
from openai.types.shared import Reasoning


lead_search_agent = Agent(
    name="LeadSearchAgent",
    description="Find and validate leads via web search, summarize candidates, and hand off approved leads for capture and outreach.",
    instructions="./instructions.md",
    files_folder="./files",
    tools_folder="./tools",
    tools=[WebSearchTool()],
    model="gpt-5.2",
    model_settings=ModelSettings(reasoning=Reasoning(effort="medium", summary="auto")),
)
