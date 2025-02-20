import discord
from discord.ext import commands
import requests
import asyncio
from io import BytesIO
import json
import urllib.parse

# 設定ファイルを読み込み
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

TOKEN = config["token"]
VOICEVOX_URL = config["voicevox_url"]
DEFAULT_CHARACTER = config["default_character"]
CHARACTER_MAP = config["character_map"]

# ユーザーごとのキャラクター設定
user_character_map = {}
server_dictionaries = {}
server_audio_playback_settings = {}  # サーバーごとの音声ファイル再生設定
active_text_channel = None  # 読み上げ対象のテキストチャンネル

# 再生中の音声を停止するためのフラグ
is_audio_playing = False

# Botの準備
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


def classify_attachment(filename):
    """ファイルの種類を分類 (拡張子ベース)"""
    extension = filename.split(".")[-1].lower()
    if extension in ["jpg", "jpeg", "png", "gif"]:
        return "画像"
    elif extension in ["mp4", "mkv", "avi", "mov"]:
        return "動画"
    elif extension in ["pdf", "txt", "doc", "docx"]:
        return "ドキュメント"
    elif extension in ["wav", "mp3", "aac", "flac"]:
        return "音声"
    else:
        return "ファイル"


def apply_custom_dictionary(guild_id, text):
    """辞書を適用してテキストを変換"""
    if guild_id not in server_dictionaries:
        return text

    for entry in server_dictionaries[guild_id]:
        surface = entry["surface"]
        pronunciation = entry["pronunciation"]
        text = text.replace(surface, pronunciation)
    return text


@bot.event
async def on_ready():
    print(f"Botとしてログインしました: {bot.user}")


@bot.command()
async def join(ctx):
    """ボイスチャンネルに接続"""
    global active_text_channel
    try:
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            await channel.connect()
            active_text_channel = ctx.channel
            await ctx.send(f"ボイスチャンネル「 {channel.name} 」に接続しました！ｷﾀ━━━━(ﾟ∀ﾟ)━━━━!!")
        else:
            await ctx.send("ボイスチャンネルに接続してからコマンドを実行してください！")
    except discord.ClientException as e:
        await ctx.send(f"既にボイスチャンネルに接続しています。({e})")
    except Exception as e:
        await ctx.send(f"ズモモエラー！！チャンネル接続のエラーが出たぞ！人間！対応しろ！: {e}")
        if ctx.voice_client:
            await generate_and_play_tts(ctx.voice_client, "ズモモエラー！！チャンネル接続のエラーが出たぞ！人間！対応しろ！。", CHARACTER_MAP[DEFAULT_CHARACTER])


@bot.command()
async def leave(ctx):
    """ボイスチャンネルから切断"""
    global active_text_channel
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        active_text_channel = None
        await ctx.send("切断しました！─=≡Σ((( つ•̀ω•́)つ")
    else:
        await ctx.send("Botはボイスチャンネルに接続していません。")


@bot.command()
async def stop(ctx):
    """再生中の音声を停止"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        global is_audio_playing
        is_audio_playing = False
        await ctx.send("再生を停止しました！")
    else:
        await ctx.send("再生中の音声がありません。")


@bot.command()
async def set(ctx, character_name: str):
    """コマンド実行者のキャラクターを設定"""
    global user_character_map

    if character_name not in CHARACTER_MAP:
        await ctx.send(f"キャラクター名 '{character_name}' は存在しません。有効なキャラクターを指定してください。")
        return

    user_character_map[ctx.author.id] = CHARACTER_MAP[character_name]
    await ctx.send(f"キャラクターを '{character_name}' に設定しました！")


@bot.command()
async def add(ctx, surface: str, pronunciation: str):
    """辞書登録機能"""
    guild_id = ctx.guild.id
    if guild_id not in server_dictionaries:
        server_dictionaries[guild_id] = []

    entry = {
        "surface": surface,
        "pronunciation": pronunciation
    }
    server_dictionaries[guild_id].append(entry)
    await ctx.send(f"辞書に単語を登録しました: {surface} ({pronunciation})")


@bot.command()
async def audioplay(ctx, state: str):
    """音声ファイルの再生設定を変更"""
    guild_id = ctx.guild.id
    if state.lower() not in ["true", "false"]:
        await ctx.send("無効な設定です。有効な値: true または false")
        return

    server_audio_playback_settings[guild_id] = state.lower() == "true"
    status = "有効" if server_audio_playback_settings[guild_id] else "無効"
    await ctx.send(f"音声ファイルの再生設定を{status}にしました！")


@bot.command()
async def help(ctx):
    """コマンドの使用方法を表示"""
    help_message = """
    **使用可能なコマンド一覧**:
    - `!join`: ボイスチャンネルに接続
    - `!leave`: ボイスチャンネルから切断
    - `!stop`: 再生中の音声を停止
    - `!set <キャラクター名>`: あなたのキャラクターを設定
    - `!add <単語> <読み>`: サーバー固有の辞書に単語を登録
    - `!audioplay <true|false>`: 音声ファイルの再生設定を変更
    - `!help`: このヘルプを表示
    """
    await ctx.send(help_message)


@bot.event
async def on_message(message):
    """メッセージ読み上げ処理"""
    await bot.process_commands(message)

    global active_text_channel
    if message.author.bot or not message.guild or active_text_channel != message.channel:
        return

    # コマンドメッセージは読み上げない
    if message.content.startswith(bot.command_prefix):
        return

    if message.guild.voice_client and message.guild.voice_client.is_connected():
        character_id = user_character_map.get(message.author.id, CHARACTER_MAP[DEFAULT_CHARACTER])
        guild_id = message.guild.id

        if message.attachments:
            for attachment in message.attachments:
                file_type = classify_attachment(attachment.filename)
                if file_type == "音声":
                    if server_audio_playback_settings.get(guild_id, True):
                        tts_text = "添付された音声ファイルを再生します。"
                        await generate_and_play_tts(message.guild.voice_client, tts_text, character_id)
                        audio_url = attachment.url
                        await play_audio_from_url(message.guild.voice_client, audio_url)
                    else:
                        tts_text = "音声ファイル添付"
                        await generate_and_play_tts(message.guild.voice_client, tts_text, character_id)
                else:
                    tts_text = f"{file_type}添付"
                    await generate_and_play_tts(message.guild.voice_client, tts_text, character_id)
        elif any(word.startswith("http") for word in message.content.split()):
            await generate_and_play_tts(message.guild.voice_client, "リンク省略", character_id)
        else:
            processed_text = apply_custom_dictionary(guild_id, message.content)
            await generate_and_play_tts(message.guild.voice_client, processed_text, character_id)


async def generate_and_play_tts(voice_client, text, character_id):
    """VOICEVOXを使ってTTSを生成し再生"""
    global is_audio_playing
    try:
        encoded_text = urllib.parse.quote(text)
        query_url = f"{VOICEVOX_URL}/audio_query?text={encoded_text}&speaker={character_id}"
        query_response = requests.post(query_url)
        query_response.raise_for_status()
        audio_query = query_response.json()

        synthesis_response = requests.post(f"{VOICEVOX_URL}/synthesis", params={"speaker": character_id}, json=audio_query)
        synthesis_response.raise_for_status()

        audio_data = BytesIO(synthesis_response.content)

        if not is_audio_playing or not voice_client.is_playing():
            is_audio_playing = True
            voice_client.play(discord.FFmpegPCMAudio(audio_data, pipe=True, executable="ffmpeg"), after=lambda e: print(f"再生終了: {e}"))
            while voice_client.is_playing():
                await asyncio.sleep(1)
            is_audio_playing = False
    except Exception as e:
        error_message = f"ズモモエラー！！TTS生成のエラーが出たぞ！人間！対応しろ！: {e}"
        print(error_message)
        if active_text_channel:
            await active_text_channel.send(error_message)
        if voice_client:
            await generate_and_play_tts(voice_client, "ズモモエラー！！TTS生成のエラーが出たぞ！人間！対応しろ！", CHARACTER_MAP[DEFAULT_CHARACTER])


async def play_audio_from_url(voice_client, url):
    """URLから音声を再生"""
    global is_audio_playing
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        audio_data = BytesIO(response.content)

        if not is_audio_playing:
            is_audio_playing = True
            voice_client.play(discord.FFmpegPCMAudio(audio_data, pipe=True, executable="ffmpeg"), after=lambda e: print(f"再生終了: {e}"))
            while voice_client.is_playing():
                await asyncio.sleep(1)
            is_audio_playing = False
    except Exception as e:
        error_message = f"ズモモエラー！！音声ファイル再生のエラーが出たぞ！人間！対応しろ！: {e}"
        print(error_message)
        if active_text_channel:
            await active_text_channel.send(error_message)
        if voice_client:
            await generate_and_play_tts(voice_client, "ズモモエラー！！音声ファイル再生のエラーが出たぞ！人間！対応しろ！", CHARACTER_MAP[DEFAULT_CHARACTER])


bot.run(TOKEN)
