import discord 
import asyncio
import aiohttp # type: ignore
from discord.ext import commands # type: ignore
intents = discord.Intents.default() 
intents.presences = True             
client = commands.Bot(command_prefix="!", intents=intents)


# ==== KONFIGURATION ====
TOKEN = ""
CHANNEL_ID = discordchannelid
GITLAB_TOKEN = ""
PROJECT_ID = ""

PORTAINER_URL = ""
PORTAINER_USERNAME = ""           # Ändra till ditt användarnamn
PORTAINER_PASSWORD = ""    # Ändra till ditt lösenord
CONTAINER_NAME = ""       # Namnet på containern

# ==== GITLAB PIPELINE STATUS ====
async def get_pipeline_status():
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    base_url = f""
    async with aiohttp.ClientSession() as session:
        # Hämta senaste pipeline
        async with session.get(f"{base_url}/pipelines", headers=headers, ssl=False) as resp:
            print("DEBUG – pipelines list status:", resp.status)
            pipelines = await resp.json()
            print("DEBUG – pipelines response:", pipelines)

            if not pipelines or "id" not in pipelines[0]:
                print("❌ Hittar ingen pipeline")
                return None
            latest_id = pipelines[0]["id"]
        # Hämta info om senaste pipeline
        async with session.get(f"{base_url}/pipelines/{latest_id}", headers=headers, ssl=False) as resp:
            print("DEBUG – pipeline detail status:", resp.status)
            pipeline_data = await resp.json()
            print("DEBUG – pipeline detail response:", pipeline_data)

            return pipeline_data.get("status")

# ==== PORTAINER LOGIN OCH CONTAINERKOLL ====
async def get_portainer_token():
    url = f"{PORTAINER_URL}/api/auth"
    payload = {
        "Username": PORTAINER_USERNAME,
        "Password": PORTAINER_PASSWORD
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, ssl=False) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("jwt")
            else:
                print("❌ Inloggning till Portainer misslyckades:", resp.status)
    return None

async def container_running(jwt_token):
    headers = {"Authorization": f"Bearer {jwt_token}"}
    url = f"{PORTAINER_URL}/api/endpoints/1/docker/containers/json"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, ssl=False) as resp:
            if resp.status == 200:
                data = await resp.json()
                for container in data:
                    if CONTAINER_NAME in container["Names"][0] and container["State"] == "running":
                        return True
            else:
                print("❌ Fel vid hämtning av containers:", resp.status)
    return False

# ==== DISCORD STATUSLOOP ====
async def update_status():
    await client.wait_until_ready()
    while not client.is_closed():
        jwt = await get_portainer_token()
        if not jwt:
            await client.change_presence(activity=discord.Game("Portainer login FAIL ❌"))
            await asyncio.sleep(60)
            continue

        pipeline_status = await get_pipeline_status()
        container_status = await container_running(jwt)

        print("DEBUG – pipeline_status:", pipeline_status)
        print("DEBUG – container_status:", container_status)

        if pipeline_status == "success" and container_status:
            activity = discord.Game("Pipeline: BUILDING 🛠️")
        elif pipeline_status == "failed":
            activity = discord.Game("Pipeline: FAILED ❌")
        elif pipeline_status == "success" and container_status:
            activity = discord.Game("Pipeline: ONLINE ✅")
        else:
            activity = discord.Game("Pipeline: OFFLINE ❌")

        await client.change_presence(activity=activity)
        await asyncio.sleep(60)


class MyClient(commands.Bot):
    async def setup_hook(self):
        self.bg_task = asyncio.create_task(update_status())
client = MyClient(command_prefix="!", intents=intents)

@client.tree.command(name="gitlab-status", description="Visar aktuell pipeline-status")
async def gitlab_status(interaction: discord.Interaction):
    print("✅ Slash-kommando kördes!")  # 👈 detta ska synas i terminalen
    await interaction.response.defer()
    status = await get_pipeline_status()
    if status:
        await interaction.followup.send(f"📦 GitLab pipeline-status: `{status.upper()}`")
    else:
        await interaction.followup.send("❌ Kunde inte hämta GitLab-status.")

@client.tree.command(name="portainer-status", description="Visar container-status")
async def portainer_status(interaction: discord.Interaction):
    print("✅ Slash-kommando kördes!")  # 👈 detta ska synas i terminalen
    await interaction.response.defer()
    jwt = await get_portainer_token()
    if not jwt:
        await interaction.followup.send("❌ Kunde inte logga in i Portainer.")
        return
    running = await container_running(jwt)
    if running:
        await interaction.followup.send("🟢 Containern körs!")
    else:
        await interaction.followup.send("🔴 Containern är stoppad.")

# ==== HJÄLPFUNKTION FÖR ROLLER ====
def has_required_role(interaction: discord.Interaction):
    allowed_roles = ["admin", "DevOps"]
    user_roles = [role.name for role in interaction.user.roles]
    return any(role in allowed_roles for role in user_roles)

@client.tree.command(name="restart-container", description="Startar om containern i Portainer")
async def restart_container(interaction: discord.Interaction):
    if not has_required_role(interaction):
        await interaction.response.send_message("❌ Du har inte behörighet att använda detta kommando.", ephemeral=True)
        return

    await interaction.response.defer()
    jwt = await get_portainer_token()
    if not jwt:
        await interaction.followup.send("❌ Kunde inte logga in i Portainer.")
        return

    headers = {"Authorization": f"Bearer {jwt}"}
    url = f"{PORTAINER_URL}/api/endpoints/1/docker/containers/json"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, ssl=False) as resp:
            data = await resp.json()
            container_id = next((c["Id"] for c in data if CONTAINER_NAME in c["Names"][0]), None)

        if not container_id:
            await interaction.followup.send("❌ Containern hittades inte.")
            return

        restart_url = f"{PORTAINER_URL}/api/endpoints/1/docker/containers/{container_id}/restart"
        async with session.post(restart_url, headers=headers, ssl=False) as resp:
            if resp.status == 204:
                await interaction.followup.send("♻️ Containern har startats om!")
            else:
                await interaction.followup.send(f"❌ Misslyckades med att starta om containern. Status: {resp.status}")


@client.tree.command(name="start-container", description="Startar containern")
async def start_container(interaction: discord.Interaction):
    if not has_required_role(interaction):
        await interaction.response.send_message("❌ Du har inte behörighet att använda detta kommando.", ephemeral=True)
        return

    await interaction.response.defer()
    jwt = await get_portainer_token()
    if not jwt:
        await interaction.followup.send("❌ Kunde inte logga in i Portainer.")
        return

    headers = {"Authorization": f"Bearer {jwt}"}
    url = f"{PORTAINER_URL}/api/endpoints/1/docker/containers/json"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, ssl=False) as resp:
            data = await resp.json()
            container_id = next((c["Id"] for c in data if CONTAINER_NAME in c["Names"][0]), None)

        if not container_id:
            await interaction.followup.send("❌ Containern hittades inte.")
            return

        start_url = f"{PORTAINER_URL}/api/endpoints/1/docker/containers/{container_id}/start"
        async with session.post(start_url, headers=headers, ssl=False) as resp:
            if resp.status == 204:
                await interaction.followup.send("🟢 Containern har startats!")
            else:
                await interaction.followup.send(f"❌ Misslyckades med att starta containern. Status: {resp.status}")


@client.tree.command(name="stop-container", description="Stoppar containern")
async def stop_container(interaction: discord.Interaction):
    if not has_required_role(interaction):
        await interaction.response.send_message("❌ Du har inte behörighet att använda detta kommando.", ephemeral=True)
        return

    await interaction.response.defer()
    jwt = await get_portainer_token()
    if not jwt:
        await interaction.followup.send("❌ Kunde inte logga in i Portainer.")
        return

    headers = {"Authorization": f"Bearer {jwt}"}
    url = f"{PORTAINER_URL}/api/endpoints/1/docker/containers/json"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, ssl=False) as resp:
            data = await resp.json()
            container_id = next((c["Id"] for c in data if CONTAINER_NAME in c["Names"][0]), None)

        if not container_id:
            await interaction.followup.send("❌ Containern hittades inte.")
            return

        stop_url = f"{PORTAINER_URL}/api/endpoints/1/docker/containers/{container_id}/stop"
        async with session.post(stop_url, headers=headers, ssl=False) as resp:
            if resp.status == 204:
                await interaction.followup.send("🔴 Containern har stoppats.")
            else:
                await interaction.followup.send(f"❌ Misslyckades med att stoppa containern. Status: {resp.status}")


@client.tree.command(name="pipeline-log", description="Hämtar logg från senaste pipeline")
async def pipeline_log(interaction: discord.Interaction):
    await interaction.response.defer()
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    base_url = f"https://git.chasacademy.dev/api/v4/projects/{PROJECT_ID}"

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{base_url}/pipelines", headers=headers, ssl=False) as resp:
            pipelines = await resp.json()
            if not pipelines or "id" not in pipelines[0]:
                await interaction.followup.send("❌ Ingen pipeline hittad.")
                return
            latest_pipeline_id = pipelines[0]["id"]

        async with session.get(f"{base_url}/pipelines/{latest_pipeline_id}/jobs", headers=headers, ssl=False) as resp:
            jobs = await resp.json()
            if not jobs:
                await interaction.followup.send("❌ Inga jobb/loggar hittades.")
                return
            log_output = ""
            for job in jobs:
                log_output += f"- {job['name']} – Status: {job['status']}\n"

            await interaction.followup.send(f"📄 Logg från pipeline:\n```{log_output}```")


@client.tree.command(name="help", description="Visar tillgängliga kommandon för boten")
async def bot_help(interaction: discord.Interaction):
    help_text = """
**Tillgängliga kommandon:**

/gitlab-status – Visar aktuell status på GitLab-pipelinen  
/portainer-status – Visar om containern körs  
/pipeline-log – Hämtar logg från senaste pipeline  
/start-container – Startar containern *(endast DevOps/Admin)*  
/stop-container – Stoppar containern *(endast DevOps/Admin)*  
/restart-container – Startar om containern *(endast DevOps/Admin)*  
/help – Visar denna hjälptext
"""
    await interaction.response.send_message(help_text)

@client.event
async def on_ready():
    await client.tree.sync()  # 👈 superviktigt för att kommandon ska synas i Discord
    print(f"Inloggad som {client.user}")

client.run(TOKEN)