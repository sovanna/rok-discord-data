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


store = aioredis.from_url(
    "redis://172.17.0.3:6379", encoding="utf-8", decode_responses=True
)

load_dotenv()
TOKEN = os.getenv("TOKEN")

REDIS_KEY_GOV_ID = "authorid:govid"
GOV_KEYS = [
    "ID",
    "BASE NAME",
    "BASE POWER",
    "BASE KILL POINTS",
    "NAME",
    "POWER",
    "KILL POINTS",
    "KVK KILLS | T4",
    "KVK KILLS | T5",
    "KVK KILLS | T4 + T5",
    "KVK DEADS",
    "CUSTOM PLAYER KILLS +",
    "CUSTOM PLAYER DEAD +",
    "EXPECTED KILLS",
    "EXPECTED DEADS",
    "EVE OF THE CRUSADE POINTS",
    "HONOR POINTS",
    "TOTAL SCORE",
    "KVK RANK",
]
GOV_KEYS_BASE = [
    "BASE POWER",
    "BASE KILL POINTS",
]
GOV_KEYS_CURRENT = [
    "NAME",
    "POWER",
    "KILL POINTS",
    "KVK KILLS | T4",
    "KVK KILLS | T5",
    "KVK KILLS | T4 + T5",
    "KVK DEADS",
    "EXPECTED KILLS",
    "EXPECTED DEADS",
    "CUSTOM PLAYER KILLS +",
    "CUSTOM PLAYER DEAD +",
]
GOV_KEYS_RESULT = [
    "EVE OF THE CRUSADE POINTS",
    "HONOR POINTS",
    "TOTAL SCORE",
    "KVK RANK",
]
GOAL_KEYS = {
    "kill": "EXPECTED KILLS",
    "dead": "EXPECTED DEADS",
    "custom_kills": "CUSTOM PLAYER KILLS +",
    "custom_dead": "CUSTOM PLAYER DEAD +",
}
GOV_GOAL_KEYS = {"kill": "KVK KILLS | T4 + T5", "dead": "KVK DEADS"}

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)


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
    authorid: str, gov_id: Optional[int] = None
) -> Optional[int]:
    memory_gov_id = None

    try:
        async with store.client() as conn:
            if gov_id is not None:
                await conn.hset(REDIS_KEY_GOV_ID, authorid, gov_id)
                return gov_id
            memory_gov_id = await conn.hget(REDIS_KEY_GOV_ID, authorid)
    except RedisError as e:
        print(e)

    if memory_gov_id is not None:
        try:
            memory_gov_id = int(memory_gov_id)
        except Exception as e:
            print(e)
            memory_gov_id = None
    return memory_gov_id


async def get_stat_governor_id(
    gov_id: int, interaction: discord.Interaction = None, channel=None
):
    kvk = KvK()
    governor = kvk.get_governor_last_data(gov_id)
    if governor is None:
        content = f"Governor {gov_id} not found in database."
        if interaction:
            return await interaction.response.send_message(content)
        elif channel:
            return await channel.send(content=content)
        else:
            return

    title = f"{governor.get('ID', '---')} - {governor.get('BASE NAME', '---')}"
    embed = discord.Embed(color=0x06B6D4)
    embed.title = title
    base_description = ""
    for k in GOV_KEYS_BASE:
        v = governor.get(k, None)
        base_description += f"**{k.lower().title()}**: {v or '---'}\n"

    base_description += "\n"

    base_description += (
        f"**Data collect on: {kvk.get_last_registered_date()} (Month/Date/Year)\n**"
    )
    base_description += "\n"
    for k in GOV_KEYS_CURRENT:
        v = governor.get(k, None)
        base_description += f"**{k.lower().title()}**: {v or '---'}\n"

    base_description += "\n"

    embed.description = base_description

    try:
        last_power = int(governor["POWER"].replace(",", ""))
        base_power = int(governor["BASE POWER"].replace(",", ""))
        last_kp = int(governor["KILL POINTS"].replace(",", ""))
        base_kp = int(governor["BASE KILL POINTS"].replace(",", ""))
        embed.add_field(
            name="Power Diff",
            value="💪 {:,}".format(last_power - base_power),
            inline=True,
        )
        embed.add_field(
            name="Kill Points Increase", value="🔥 {:,}".format(last_kp - base_kp)
        )
        embed.add_field(name="\u200B", value="\u200B")

        embed.add_field(
            name="Eve Of The Crusade",
            value=governor.get("EVE OF THE CRUSADE POINTS", "---"),
            inline=True,
        )
        embed.add_field(
            name="Honor Points", value=governor.get("HONOR POINTS", "---"), inline=True
        )
        embed.add_field(name="\u200B", value="\u200B")

        embed.add_field(
            name="Total Score", value=governor.get("TOTAL SCORE", "---"), inline=True
        )
        embed.add_field(
            name="Kvk Rank", value=governor.get("KVK RANK", "---"), inline=True
        )
        embed.add_field(name="\u200B", value="\u200B")
    except Exception as _:
        pass

    gov_goal_set = True
    for _, v in GOAL_KEYS.items():
        if v not in governor:
            gov_goal_set = False
    for _, v in GOV_GOAL_KEYS.items():
        if v not in governor:
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
            gov_goal_kill = int(governor[GOAL_KEYS.get("kill")].replace(",", ""))
            gov_goal_dead = int(governor[GOAL_KEYS.get("dead")].replace(",", ""))
            goal_to_reached = gov_goal_kill + gov_goal_dead

            custom_kills = governor.get(GOAL_KEYS.get("custom_kills"), None)
            custom_kills = int(custom_kills.replace(",", "")) if custom_kills else 0
            custom_dead = governor.get(GOAL_KEYS.get("custom_dead"), None)
            custom_dead = int(custom_dead.replace(",", "")) if custom_dead else 0

            gov_kill = int(governor[GOV_GOAL_KEYS.get("kill")].replace(",", ""))
            gov_dead = int(governor[GOV_GOAL_KEYS.get("dead")].replace(",", ""))
            gov_reached = gov_kill + gov_dead

            gov_progression = round(gov_reached * 100 / goal_to_reached)
            kill_met = gov_kill >= gov_goal_kill
            dead_met = gov_dead >= gov_goal_dead
            custom_kill_met = gov_kill >= gov_goal_kill + custom_kills
            custom_dead_met = gov_dead >= gov_goal_dead + custom_dead
        except Exception as e:
            print(e)

        if gov_progression is not None:
            embed.add_field(
                name="KD Expected Kills",
                value=f"{'✅' if kill_met else '🚫'}",
                inline=True,
            )
            embed.add_field(
                name="KD Expected Deads", value=f"{'✅' if dead_met else '🚫'}"
            )
            embed.add_field(name="\u200B", value="\u200B")
            if custom_kills > 0:
                embed.add_field(
                    name="Player Expected Kills",
                    value=f"{'✅' if custom_kill_met else '🚫'}",
                    inline=True,
                )
            else:
                embed.add_field(
                    name="Player Expected Kills",
                    value="---",
                    inline=True,
                )

            if custom_dead > 0:
                embed.add_field(
                    name="Player Expected Dead",
                    value=f"{'✅' if custom_dead_met else '🚫'}",
                    inline=True,
                )
            else:
                embed.add_field(
                    name="Player Expected Dead",
                    value="---",
                    inline=True,
                )

            embed.add_field(name="\u200B", value="\u200B")
            embed.add_field(
                name="Global Kill/Dead Progression", value=f"{gov_progression}%"
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
    try:
        async with store.client() as conn:
            pong = await conn.ping()
            print(f"Redis ping: {'pong' if pong else '---'}")
    except RedisError as e:
        print(e)


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
        except Exception as e:
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


async def main():
    await bot.start(TOKEN, reconnect=True)


asyncio.run(main())
