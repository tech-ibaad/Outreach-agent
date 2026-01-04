from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning


outreach_agent = Agent(
    name="OutreachAgent",
    description="Owns Notion lead database operations and Resend email delivery with explicit user approval steps.",
    instructions="./instructions.md",
    files_folder="./files",
    tools_folder="./tools",
    model="gpt-5.2",
    model_settings=ModelSettings(reasoning=Reasoning(effort="medium", summary="auto")),
)
