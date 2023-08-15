import os
import requests
import time
import typer
from dotenv import load_dotenv

load_dotenv()
APPLICATION_ID = os.getenv("APPLICATION_ID")
TOKEN = os.getenv("TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

app = typer.Typer()

URL_BASE = f"https://discord.com/api/v10/applications/{APPLICATION_ID}/commands"
HEADERS_BASE = {"Authorization": f"Bot {TOKEN}"}


@app.command()
def hello():
    print(f"=== CLI: Manage Slash Commands for Discord Bot ===")


@app.command()
def list_commands():
    resp = requests.get(URL_BASE, headers=HEADERS_BASE)
    try:
        data = resp.json()
        print(f"List Commands: {data}")
        return data
    except Exception as e:
        print(e)


@app.command()
def list_ids_commands():
    data = list_commands()
    if data is not None:
        ids = [e["id"] for e in data]
        print(f"List ID Commands: {ids}")
        return ids
    return []


@app.command()
def reset():
    ids = list_ids_commands()
    for id in ids:
        resp = requests.delete(f"{URL_BASE}/{id}", headers=HEADERS_BASE)
        time.sleep(2)
        print(f"COMMAND ID {id}: {resp.status_code}")


if __name__ == "__main__":
    app()
