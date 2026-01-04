from dotenv import load_dotenv
from agency_swarm import Agency
from dotenv import load_dotenv

from lead_search_agent import lead_search_agent
from outreach_agent import outreach_agent

load_dotenv()

# do not remove this method, it is used in the main.py file to deploy the agency (it has to be a method)
def create_agency(load_threads_callback=None):
    agency = Agency(
        lead_search_agent,
        communication_flows=[
            (lead_search_agent, outreach_agent),
            (outreach_agent, lead_search_agent),
        ],
        name="LeadSearchOutreachAgency",
        shared_instructions="shared_instructions.md",
        load_threads_callback=load_threads_callback,
    )

    return agency

if __name__ == "__main__":
    agency = create_agency()

    # test 1 message
    # async def main():
    #     response = await agency.get_response("Hello, how are you?")
    #     print(response)
    # asyncio.run(main())

    # run in terminal
    agency.terminal_demo()
