import asyncio
import discord
import os
from discord.ext import commands
from dotenv import load_dotenv
from quickchart import QuickChart
from redis import asyncio as aioredis
from redis import RedisError
from typing import Optional
from gsheets import KvK

load_dotenv()

# Setup Redis - Storage for quick access
REDIS_HOSTNAME = os.getenv("REDIS_HOSTNAME")
REDIS_PORT = os.getenv("REDIS_PORT")
store: aioredis.Redis | None = None
if REDIS_HOSTNAME and REDIS_PORT:
    store = aioredis.from_url(
        f"redis://{REDIS_HOSTNAME}:{REDIS_PORT}",
        encoding="utf-8",
        decode_responses=True,
    )

KINGDOM = os.getenv("KINGDOM")
STORE_GOV_ID = f"{KINGDOM}:authorid:govid"
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Values should match the columns' name
# from Google Sheet document.
MODEL = {
    "id": "ID",
    "base_name": "BASE NAME",
    "base_power": "BASE POWER",
    "base_kp": "BASE KILL POINTS",
    "last_name": "LAST NAME",
    "last_power": "LAST POWER",
    "last_kp": "LAST KILL POINTS",
    "kvk_t4": "KVK KILLS | T4",
    "kvk_t5": "KVK KILLS | T5",
    "kvk_t4_t5": "KVK KILLS | T4 + T5",
    "kvk_deads": "KVK DEADS",
    "kd_goal_kills": "KD GOAL KILLS",
    "kd_goal_deads": "KD GOAL DEADS",
    "pl_goal_kills": "PLAYER GOAL KILLS+",
    "pl_goal_deads": "PLAYER GOAL DEAD+",
    "eve": "EVE OF THE CRUSADE POINTS",
    "hp": "HONOR POINTS",
    "score": "TOTAL SCORE",
    "rank": "KVK RANK",
}

GOV = list(MODEL.values())

UI_GOV_BASE = [
    MODEL.get("base_power"),
    MODEL.get("base_kp"),
]
UI_GOV_CURRENT_SECTION_1 = [
    MODEL.get("last_name"),
    MODEL.get("last_power"),
    MODEL.get("last_kp"),
]
UI_GOV_CURRENT_SECTION_2 = [
    MODEL.get("kvk_t4"),
    MODEL.get("kvk_t5"),
    MODEL.get("kvk_t4_t5"),
    MODEL.get("kvk_deads"),
    MODEL.get("kd_goal_kills"),
    MODEL.get("kd_goal_deads"),
]
UI_GOV_RESULT = [
    MODEL.get("eve"),
    MODEL.get("hp"),
    MODEL.get("score"),
    MODEL.get("rank"),
]

KD_GOAL = {
    "kill": MODEL.get("kd_goal_kills"),
    "dead": MODEL.get("kd_goal_deads"),
    "player_kills": MODEL.get("pl_goal_kills"),
    "player_dead": MODEL.get("pl_goal_deads"),
}
GOV_TRACK = {
    "kill": MODEL.get("kvk_t4_t5"),
    "dead": MODEL.get("kvk_deads"),
}

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="/",
    intents=intents,
    help_command=None,
)


def get_chart_url(progress=0):
    qc = QuickChart()
    qc.width = 500
    qc.height = 300
    qc.version = "2.9.4"
    qc.config = """{
        type: 'gauge',
        data: {
            datasets: [
            {
                value: %i,
                data: [50, 100, 150, 200],
                backgroundColor: ['#D64545', '#4098D7', '#3EBD93', 'black'],
                borderWidth: 2,
            },
            ],
        },
        options: {
            valueLabel: {
            fontSize: 24,
            backgroundColor: 'transparent',
            color: '#000',
            formatter: function (value, context) {
                return %i + ' %%';
            },
            bottomMarginPercentage: 10,
            },
        },
        }""" % (
        progress if progress <= 200 else 200,
        progress,
    )
    return qc.get_url()


async def get_id_from_store(
    authorid: str,
    gov_id: Optional[int] = None,
) -> Optional[int]:
    if not store:
        return None
    try:
        async with store.client() as conn:
            if gov_id is not None:
                await conn.hset(STORE_GOV_ID, authorid, gov_id)
                return gov_id
            memory_gov_id = await conn.hget(STORE_GOV_ID, authorid)
            if memory_gov_id:
                memory_gov_id = int(memory_gov_id)
            return memory_gov_id
    except RedisError as e:
        print(e)
    except Exception as e:
        print(e)
    return None


async def get_stat_governor_id(
    gov_id: int,
    interaction: Optional[discord.Interaction] = None,
    channel=None,
):
    kvk = KvK()

    governor = kvk.get_governor_last_data(gov_id)
    if governor is None:
        content = f"Governor {gov_id} not found in database."
        if interaction:
            return await interaction.response.send_message(content)
        elif channel:
            return await channel.send(content=content)
        return

    embed = discord.Embed(color=0x06B6D4)
    embed.title = f"{governor.get(MODEL.get('id'), '---')} - {governor.get(MODEL.get('base_name'), '---')}"

    base_description = ""
    for k in UI_GOV_BASE:
        if not k:
            continue
        v = governor.get(k, None)
        base_description += f"**{k.lower().title()}**: {v or '---'}\n"
    base_description += "\n"
    base_description += (
        f"**Data collect on: {kvk.get_last_registered_date()} (Month/Date/Year)\n**"
    )
    base_description += "\n"
    for k in UI_GOV_CURRENT_SECTION_1:
        if not k:
            continue
        v = governor.get(k, None)
        base_description += f"**{k.lower().title()}**: {v or '---'}\n"
    base_description += "\n"
    for k in UI_GOV_CURRENT_SECTION_2:
        if not k:
            continue
        v = governor.get(k, None)
        base_description += f"**{k.lower().title()}**: {v or '---'}\n"
    base_description += "\n"
    embed.description = base_description

    try:
        last_power = int(governor.get(MODEL.get("last_power"), "0").replace(",", ""))
        base_power = int(governor.get(MODEL.get("base_power"), "0").replace(",", ""))
        last_kp = int(governor.get(MODEL.get("last_kp"), "0").replace(",", ""))
        base_kp = int(governor.get(MODEL.get("base_kp"), "0").replace(",", ""))
        power_diff = last_power - base_power
        power_diff_format = "{:,}".format(power_diff)
        power_emoji = f"{'🧐' if power_diff > 0 else '💪'}"
        embed.add_field(
            name="Power Diff",
            value=f"{power_emoji} {power_diff_format}",
            inline=True,
        )
        embed.add_field(
            name="Kill Points Increase",
            value="🔥 {:,}".format(last_kp - base_kp),
        )
        embed.add_field(name="\u200B", value="\u200B")

        embed.add_field(
            name="Total Score",
            value=governor.get(MODEL.get("score"), "N/A"),
            inline=True,
        )
        embed.add_field(
            name="KvK Rank",
            value=governor.get(MODEL.get("rank"), "N/A"),
            inline=True,
        )
        embed.add_field(name="\u200B", value="\u200B")
    except Exception as e:
        print(e)

    gov_goal_set = True
    for _, v in KD_GOAL.items():
        if v not in governor:
            print(f"{v} is not in governor")
            gov_goal_set = False
    for _, v in GOV_TRACK.items():
        if v not in governor:
            print(f"{v} is not in governor")
            gov_goal_set = False

    if gov_goal_set is True:
        gov_progression = None
        kill_met = None
        dead_met = None
        custom_kill_met = None
        custom_dead_met = None
        custom_kills = 0
        custom_dead = 0
        try:
            gov_goal_kill = int(governor.get(KD_GOAL.get("kill"), "0").replace(",", ""))
            gov_goal_dead = int(governor.get(KD_GOAL.get("dead"), "0").replace(",", ""))
            goal_to_reached = gov_goal_kill + gov_goal_dead

            custom_kills = governor.get(KD_GOAL.get("player_kills"), None)
            custom_kills = int(custom_kills.replace(",", "")) if custom_kills else 0
            custom_dead = governor.get(KD_GOAL.get("player_dead"), None)
            custom_dead = int(custom_dead.replace(",", "")) if custom_dead else 0

            gov_kill = int(governor.get(GOV_TRACK.get("kill"), "0").replace(",", ""))
            gov_dead = int(governor.get(GOV_TRACK.get("dead"), "0").replace(",", ""))
            gov_reached = gov_kill + gov_dead

            if goal_to_reached > 0:
                gov_progression = round(gov_reached * 100 / goal_to_reached)

            kill_met = gov_kill >= gov_goal_kill
            dead_met = gov_dead >= gov_goal_dead
            custom_kill_met = gov_kill >= custom_kills
            custom_dead_met = gov_dead >= custom_dead
        except Exception as e:
            print(e)

        if gov_progression is not None:
            if custom_kills > 0:
                embed.add_field(
                    name="Player Goal Kills",
                    value=f"{'✅' if custom_kill_met else '🚫'}",
                    inline=True,
                )
            else:
                embed.add_field(
                    name="KD Goal Kills",
                    value=f"{'✅' if kill_met else '🚫'}",
                    inline=True,
                )

            if custom_dead > 0:
                embed.add_field(
                    name="Player Goal Dead",
                    value=f"{'✅' if custom_dead_met else '🚫'}",
                    inline=True,
                )
            else:
                embed.add_field(
                    name="KD Goal Deads",
                    value=f"{'✅' if dead_met else '🚫'}",
                )

            embed.add_field(name="\u200B", value="\u200B")
            embed.add_field(
                name="Global Kill/Dead Progression",
                value=f"{gov_progression}%",
            )
            chart_url = get_chart_url(progress=gov_progression)
            embed.set_image(url=chart_url)

    if interaction:
        await interaction.response.send_message(embed=embed)
    elif channel:
        await channel.send(embed=embed)


@bot.hybrid_command(name="stat")
async def stat(ctx):
    interaction: discord.Interaction = ctx.interaction
    data = interaction.data
    # for the stats command, with only have one option (PLAYER ID)
    options = data["options"]
    option = options[0]
    value = option["value"]
    gov_id = None

    try:
        gov_id = int(value)
    except Exception as e:
        # maybe not a valid player ID
        print(e)

    if gov_id is None:
        await interaction.response.send_message(
            "Sorry! you entered a non valid GOVERNOR ID", ephemeral=True
        )
    else:
        await get_stat_governor_id(gov_id=gov_id, interaction=interaction)


@bot.hybrid_command(name="top")
async def top(ctx):
    interaction: discord.Interaction = ctx.interaction
    ranking = KvK().get_top_governors(top=100)
    chunked_list = []
    chunked_size = 20
    for i in range(0, len(ranking), chunked_size):
        chunked_list.append(ranking[i : i + chunked_size])

    embed_list = []
    for idx, chunked in enumerate(chunked_list):
        l = len(chunked)
        start = idx * chunked_size + 1
        end = idx * chunked_size + l

        content = ""
        for i, row in enumerate(chunked):
            content += f"#{'0' if (start+i) < 10 else ''}{start+i} | {row['id']} | {row['name']} | {row['score']} pts\n"
        content += ""

        embed = discord.Embed(color=0x0000FF)
        embed.title = f"TOP by TOTAL SCORE"
        embed.add_field(name=f"{start} -> {end}", value=content)
        embed_list.append(embed)

    try:
        await interaction.response.send_message(embeds=embed_list)
    except Exception as e:
        await interaction.response.send_message(str(e))


@bot.event
async def on_command_error(ctx, error):
    interaction: discord.Integration = ctx.interaction

    if isinstance(error, commands.MissingRole):
        await interaction.response.send_message(
            content="You don't have appropriate Role", ephemeral=True
        )
    elif isinstance(error, commands.CommandError):
        await interaction.response.send_message(
            content=f"Invalid command {str(error)}", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            content="An error occurred", ephemeral=True
        )


@bot.event
async def on_ready():
    if store:
        try:
            async with store.client() as conn:
                pong = await conn.ping()
                print(f"Redis ping: {'pong' if pong else '---'}")
        except RedisError as e:
            print(e)
    else:
        print("Redis is missing")


@bot.event
async def on_message(message):
    author = message.author
    author_id = author.id
    content = message.content
    channel = message.channel

    if not content or content.strip() == "":
        return

    gov_id = None

    cmd = content.split(" ")
    cmd_length = len(cmd)
    if cmd_length == 2:
        cmd_name = cmd[0]
        gov_id = cmd[1]
        if cmd_name.lower() != "stat":
            return
        try:
            gov_id = int(gov_id)
        except Exception as _:
            return await channel.send(content="Governor ID is not valid.")
        gov_id = await get_id_from_store(authorid=author_id, gov_id=gov_id)
    elif cmd_length == 1:
        cmd_name = cmd[0]
        if cmd_name.lower() != "stat":
            return
        gov_id = await get_id_from_store(authorid=author_id)
    else:
        return

    if gov_id is None:
        return await channel.send(
            content="Governor ID not found in memory. Please try with the full command: `stat 1234` (where 1234 is your Governor ID)"
        )

    await get_stat_governor_id(gov_id=gov_id, channel=channel)


async def main(token: str):
    await bot.start(token, reconnect=True)


if DISCORD_TOKEN:
    asyncio.run(main(DISCORD_TOKEN))
else:
    print("DISCORD_TOKEN is missing in environment variables.")
