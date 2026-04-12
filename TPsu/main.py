import os
import time
from pydoc import describe
from typing import Annotated

import aiohttp
import discord
from discord.ext import commands ,tasks
import logging
import osu
from osu import Client, GameModeStr, Mods, Mod, UserScoreType
from dotenv import load_dotenv
import mysql.connector
import typing


load_dotenv()
token = os.getenv("DISCORD_TOKEN")
client_id = os.getenv("client_id")
client_secret = os.getenv("client_secret")

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='-', intents=intents)

client = Client.from_credentials(client_id, client_secret, None)


mode = 'osu'
db = mysql.connector.connect(host="localhost",
                             user="root",
                             passwd="root",
                             database="osu",
                             autocommit=True)
channelID = 0
ruleID = ""

mycursor = db.cursor()

notFound = "You are not linked to any user in TPsu Database \n use -link <yourBeutifulUsername> to link it"



def readable_mod(mods):
    if not mods:
        return "**NoMod**"
    if isinstance(mods, Mods):
        return "**"+"+" + mods.to_readable_string()+"**"
    return "**"+ "+" .join(map(lambda x: x.mod.value, mods))+"**"


@bot.event
async def on_ready():
    global channelID
    sql = "SELECT setting_value FROM BotSettings WHERE setting_name = 'last_announcement_channel'"
    mycursor.execute(sql)
    result = mycursor.fetchone()

    if result is not None:
        # Force convert to int to ensure get_channel works
        channelID = int(result[0])
        print(f"Logged in as {bot.user}. Target channel: {channelID}")
    global ruleID
    sql = "SELECT setting_value FROM BotSettings WHERE setting_name = 'Rule to mention'"
    mycursor.execute(sql)
    result = mycursor.fetchone()

    if result is not None:
        # Force convert to int to ensure get_channel works
        ruleID = int(result[0])
    if not checkusers.is_running():
        checkusers.start()
@bot.event
async def on_dissconnect():
    checkusers.stop()
    mycursor.close()

@bot.command()
async def link(ctx ,*,msg):
    sql = "SELECT DiscordID FROM DiscordConnection WHERE DiscordID = (%s)"
    val = (str(ctx.author.id),)

    mycursor.execute(sql, val)

    result = mycursor.fetchone()
    if result is not None:
        await ctx.send("You are already linked to TPsu Database")
        return

    users = client.lookup_users(msg)
    user = users[0]


    sql = "INSERT INTO DiscordConnection (DiscordID, OsuID) VALUES (%s,%s)"
    val = (ctx.author.id, int(user.id))
    mycursor.execute(sql, val)
    top_scores = client.get_user_scores(user.id, UserScoreType.BEST, limit=3)

    sql = "INSERT INTO TopPlays (OsuID, 1stBeatmap, 1stPP, 2ndBeatmap, 2ndPP, 3rdBeatmap, 3rdPP) VALUES (%s,%s,%s,%s,%s,%s,%s)"
    val = (int(user.id)
               , int(top_scores[0].beatmapset.id), float(top_scores[0].pp)
                ,int(top_scores[1].beatmapset.id), float(top_scores[1].pp)
                ,int(top_scores[2].beatmapset.id), float(top_scores[2].pp))
    mycursor.execute(sql, val)

    await ctx.send(f"https://osu.ppy.sh/u/{user.id} connected to,{ctx.author.id} or {ctx.author.display_name}")

@bot.command()
async def unlink(ctx):
    sql = "DELETE FROM TopPlays WHERE OsuID = (%s)"
    val = (get_OsuID(ctx.author.id),)
    mycursor.execute(sql, val)

    sql = "DELETE FROM DiscordConnection WHERE DiscordID = (%s)"
    val = (ctx.author.id,)
    mycursor.execute(sql, val)
    await ctx.send("You are seccefully unlinked from TPsu Database")





@bot.command()
async def top(ctx, * ,msg: typing.Optional[str] = None):

    user_id = ""
    if msg is None:
        user_id = get_OsuID(str(ctx.author.id))
        if user_id is notFound:
            await ctx.send(user_id)
            return
    else:
      users = client.lookup_users(msg)
      user_id = users[0].id

    top_scores = client.get_user_scores(int(user_id), UserScoreType.BEST, limit=3)


    string = ""
    for i, score in enumerate(top_scores):
        string+= f"{i + 1}. {score.beatmapset.artist} - {score.beatmapset.title}: {score.pp}pp - {readable_mod(score.mods)} \n"
    embeded = discord.Embed(title="Top Scores",description=string)
    massage = await ctx.send(embed=embeded)
    await massage.add_reaction("🔥")

@bot.command()
async def linkChannel(ctx):
    global channelID
    channelID = ctx.channel.id

    sql = "REPLACE INTO BotSettings (setting_name, setting_value) VALUES (%s, %s)"
    val = ("last_announcement_channel", channelID)
    mycursor.execute(sql, val)

    await ctx.send(f"Channel saved to database! TPsu is linked to {ctx.channel}")

    if not checkusers.is_running():
        checkusers.start()

@bot.command()
async def linkRule(ctx , *, msg):
    global ruleID
    ruleID = msg

    sql = "REPLACE INTO BotSettings (setting_name, setting_value) VALUES (%s, %s)"
    val = ("Rule to mention", ruleID )
    mycursor.execute(sql, val)

    await ctx.send(f"Rule saved to database! TPsu is linked to {ruleID}")

@bot.command()
async def shutdown(ctx):
    mycursor.close()
    db.close()
    await bot.close()



def get_OsuID(author_id):
    sql = "SELECT OsuID FROM DiscordConnection WHERE DiscordID = %s"
    val = (str(author_id),)
    mycursor.execute(sql, val)

    result = mycursor.fetchone()

    if result is None:
        return notFound

    osu_id = result[0]
    return osu_id


def getBeatmapID(id):
    beatmap_id = []

    sql = "SELECT * FROM topPlays WHERE OsuID = %s"
    val = (id,)
    mycursor.execute(sql, val)
    result = mycursor.fetchone()
    i = 1
    while(i < len(result)):
        if i % 2 == 1:
            beatmap_id.append(result[i])
        i += 1
    return beatmap_id

def getBeatmapPP(id):
    beatmap_pp = []

    sql = "SELECT * FROM topPlays WHERE OsuID = %s"
    val = (id,)
    mycursor.execute(sql, val)
    result = mycursor.fetchone()
    i = 1
    while(i < len(result)):
        if i % 2 == 0:
            beatmap_pp.append(result[i])
        i += 1

    return beatmap_pp


def changeData(cursor, num, id, map, pp):  # Pass the cursor as an argument
    col_config = {
        0: ("1stBeatmap", "1stPP"),
        1: ("2ndBeatmap", "2ndPP"),
        2: ("3rdBeatmap", "3rdPP")
    }

    col_map, col_pp = col_config[num]
    sql = f"UPDATE TopPlays SET `{col_map}` = %s, `{col_pp}` = %s WHERE OsuID = %s"
    val = (int(map), float(pp), int(id))

    try:
        cursor.execute(sql, val)  # Use the passed cursor
        print(f"Success: Updated {col_map} for OsuID {id}.")
    except Exception as e:
        print(f"SQL Error: {e}")


@tasks.loop(seconds=10)
async def checkusers():
    global channelID
    global ruleID
    # Try cache first
    channel = bot.get_channel(channelID)

    # If cache is empty, try to fetch it from the API
    if channel is None:
        try:
            channel = await bot.fetch_channel(channelID)
        except Exception as e:
            print(f"Failed to fetch channel {channelID}: {e}")
            return


    cursor = db.cursor(buffered=True)
    cursor.execute("SELECT * FROM TopPlays")
    players = cursor.fetchall()

    for row in players:
        # row[0]=OsuID, row[1]=1stB, row[2]=1stPP, row[3]=2ndB, row[4]=2ndPP, etc.
        osu_id = row[0]
        stored_data = {
            0: {"id": row[1], "pp": row[2]},
            1: {"id": row[3], "pp": row[4]},
            2: {"id": row[5], "pp": row[6]}
        }

        top_scores = client.get_user_scores(osu_id, UserScoreType.BEST, limit=3)
        user = client.get_user(osu_id)
        player_name = user.username

        changed = False
        for i, score in enumerate(top_scores):
            # Compare current score to stored database score
            if int(score.beatmapset.id) != stored_data[i]["id"] or float(score.pp) != float(stored_data[i]["pp"]):
                changed = True

                # Send Embed
                mention = f"<@&{ruleID}>"
                print(str(mention))
                await channel.send(content=mention)
                url = f"https://osu.ppy.sh/beatmapsets/{score.beatmapset.id}#osu/{score.beatmap.id}"
                desc = f"[{score.beatmapset.title}]({url}) - **{score.pp}pp** - {readable_mod(score.mods)}"
                embed = discord.Embed(title=f"{user.username} Got a new Top Score #{i + 1}", description=desc)
                await channel.send(embed=embed)

                # Update Database
                changeData(cursor, i, osu_id, score.beatmapset.id, score.pp)
        if changed:
            string = ""
            for i, score in enumerate(top_scores):
                string += f"{i + 1}. {score.beatmapset.artist} - {score.beatmapset.title}: **{score.pp}pp** - {readable_mod(score.mods)} \n"
            embeded = discord.Embed(title=f"{player_name} Best Perofrmance{i + 1}", description=string)
            await channel.send(embed=embeded)
    mycursor.close()




bot.run(token,log_handler=handler,log_level=logging.DEBUG)








