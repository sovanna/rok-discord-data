import asyncio
import discord
import logging
import logging.handlers
import os
from dotenv import load_dotenv
from quickchart import QuickChart
from redis import asyncio as aioredis
from redis import RedisError
from typing import Optional
from gsheets import KvK

logger = logging.getLogger("discord")
logger.setLevel(logging.DEBUG)
logging.getLogger("discord.http").setLevel(logging.INFO)

handler = logging.handlers.RotatingFileHandler(
    filename="discord.log",
    encoding="utf-8",
    maxBytes=1 * 1024 * 1024,  # 3 MiB
    backupCount=3,  # Rotate through 3 files
)
dt_fmt = "%Y-%m-%d %H:%M:%S"
formatter = logging.Formatter(
    "[{asctime}] [{levelname:<8}] {name}: {message}", dt_fmt, style="{")
handler.setFormatter(formatter)
logger.addHandler(handler)

store = aioredis.from_url(
    "redis://0.0.0.0:6379",
    encoding="utf-8",
    decode_responses=True
)

load_dotenv()
TOKEN = os.getenv("TOKEN")

REDIS_KEY_GOV_ID = "authorid:govid"
GOV_KEYS = ["ID", "NAME", "POWER", "KVK RANK", "KVK KILLS T4", "KVK KILLS T5",
            "KVK KILLS T4/T5", "KVK DEADS", "EXPECTED KILLS", "EXPECTED DEADS", "TOTAL SCORE"]
GOAL_KEYS = {
    "kill": "EXPECTED KILLS",
    "t4": "KVK KILLS T4",
    "t5": "KVK KILLS T5",
    "dead": "EXPECTED DEADS",
}
GOV_GOAL_KEYS = {
    "kill": "KVK KILLS T4/T5",
    "t4": "KVK KILLS T4",
    "t5": "KVK KILLS T5",
    "dead": "KVK DEADS"
}

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


def get_chart_url(t4=0, t5=0, dead=0, progress=0):
    qc = QuickChart()
    qc.width = 500
    qc.height = 300
    qc.version = '2.9.4'
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
        }""" % (progress if progress <= 200 else 200, progress)
    return qc.get_url()


async def get_id_from_store(authorid: str, gov_id: Optional[int] = None) -> Optional[int]:
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


async def get_stat_governor_id(gov_id: int, channel):
    kvk = KvK()
    governor = kvk.get_governor_last_data(gov_id)
    if governor is None:
        return await channel.send(content=f"Governor {gov_id} not found in database.")

    title = f"Registration date: {kvk.get_last_registered_date()} (Month/Date/Year)\n"

    description = ""
    for k in GOV_KEYS:
        v = governor.get(k, None)
        description += f"**{k.lower().title()}**: {v or '---'}\n"

    embed = discord.Embed(color=0x00ff00)
    embed.title = title
    embed.description = description

    gov_goal_set = True
    for _, v in GOAL_KEYS.items():
        if v not in governor:
            gov_goal_set = False
    for _, v in GOV_GOAL_KEYS.items():
        if v not in governor:
            gov_goal_set = False

    if gov_goal_set is True:
        gov_progression = None

        try:
            gov_goal_kill = int(
                governor[GOAL_KEYS.get("kill")].replace(",", ""))
            gov_goal_dead = int(
                governor[GOAL_KEYS.get("dead")].replace(",", ""))
            goal_to_reached = gov_goal_kill + gov_goal_dead

            gov_kill = int(
                governor[GOV_GOAL_KEYS.get("kill")].replace(",", ""))
            gov_kill_t4 = int(
                governor[GOV_GOAL_KEYS.get("t4")].replace(",", ""))
            gov_kill_t5 = int(
                governor[GOV_GOAL_KEYS.get("t5")].replace(",", ""))
            gov_dead = int(
                governor[GOV_GOAL_KEYS.get("dead")].replace(",", ""))
            gov_reached = gov_kill + gov_dead

            gov_progression = round(gov_reached * 100 / goal_to_reached)
            gov_progression_t4 = round(gov_kill_t4 * 100 / gov_goal_kill)
            gov_progression_t5 = round(gov_kill_t5 * 100 / gov_goal_kill)
            gov_progression_dead = round(gov_dead * 100 / gov_goal_dead)
        except Exception as e:
            print(e)

        if gov_progression is not None:
            embed.add_field(name="Kill/Dead Goal Progression",
                            value=f"{gov_progression}%")
            chart_url = get_chart_url(
                t4=gov_progression_t4,
                t5=gov_progression_t5,
                dead=gov_progression_dead,
                progress=gov_progression
            )
            embed.set_image(url=chart_url)

    await channel.send(embed=embed)


@client.event
async def on_ready():
    try:
        async with store.client() as conn:
            pong = await conn.ping()
            print(f"Redis ping: {'pong' if pong else '---'}")
    except RedisError as e:
        print(e)
    print(f'We have logged in as {client.user}')


@client.event
async def on_message(message):
    author = message.author
    author_id = author.id
    content = message.content
    channel = message.channel

    if author == client.user:
        return

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
        return await channel.send(content="Governor ID not found in memory. Please try with the full command: `stat 1234` (where 1234 is your Governor ID)")

    await get_stat_governor_id(gov_id=gov_id, channel=channel)


async def main():
    await client.start(TOKEN, reconnect=True)


asyncio.run(main())
