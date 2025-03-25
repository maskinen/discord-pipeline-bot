import discord
import asyncio
import aiohttp

TOKEN = ""
CHANNEL_ID = 
GITLAB_TOKEN = ""
PROJECT_ID = "64"
PORTAINER_TOKEN = "din_portainer_token"
PORTAINER_URL = "http://localhost:9000"
CONTAINER_NAME = ""

intents = discord.Intents.default()
client = discord.Client(intents=intents)

async def get_pipeline_status():
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    url = f"https/{PROJECT_ID}/pipelines/latest"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            print("DEBUG – GitLab HTTP status:", resp.status)
            data = await resp.json()
            print("DEBUG – GitLab response:", data)
            print("DEBUG – GitLab JSON keys:", data.keys())
            if resp.status == 200:
                return data.get("status") 
    return None

async def container_running():
    headers = {"X-API-Key": PORTAINER_TOKEN}
    url = f"{PORTAINER_URL}/api/endpoints/1/docker/containers/json"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            for container in data:
                if CONTAINER_NAME in container["Names"][0] and container["State"] == "running":
                    return True
    return False

async def update_status():
    await client.wait_until_ready()
    while not client.is_closed():
        pipeline_status = await get_pipeline_status()
        container_status = await container_running()

        if pipeline_status in ("passed", "success") and container_status:
            activity = discord.Game("Pipeline: ONLINE")
        else:
            activity = discord.Game("Pipeline: OFFLINE")

        await client.change_presence(activity=activity)
        await asyncio.sleep(60)
print("DEBUG – pipeline_status:", pipeline_status)

@client.event
async def on_ready():
    print(f"Inloggad som {client.user}")

client.loop.create_task(update_status())
client.run(TOKEN)
