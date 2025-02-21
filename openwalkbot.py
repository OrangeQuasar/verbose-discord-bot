import discord
from discord.ext import commands
import requests
import asyncio
from io import BytesIO
import json
import urllib.parse
import numpy as np
from pydub import AudioSegment
import os

#設定ファイルを読み込み
with open("config.json", "r", encoding="utf-8") as readjson1:
    config = json.load(readjson1)

TOKEN = config["token"]
DEFAULT_CHARACTER = config["default_character"]
CHARACTER_MAP = config["character_map"]
SAVE_DIR = config["mp3_directory"]
OUTPUT_CHANNELID = config["recording_output_cnannelID"]

#ユーザーごとのキャラクター設定(なにこれ?)
user_character_map = {}
server_dictionaries = {}
server_audio_playback_settings = {}  # サーバーごとの音声ファイル再生設定
active_text_channel = None  # 読み上げ対象のテキストチャンネル

#再生中の音声を停止するためのフラグ
is_audio_playing = False

#Botの準備(なにこれ?)
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.voice_states = True
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

#ファイル拡張子判別
def classify_attachment(filename):
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

#なにこれ?
def apply_custom_dictionary(guild_id, text):
    if guild_id not in server_dictionaries:
        return text

    for entry in server_dictionaries[guild_id]:
        surface = entry["surface"]
        pronunciation = entry["pronunciation"]
        text = text.replace(surface, pronunciation)
    return text

#botログイン
@bot.event
async def on_ready():
    print(f"Botとしてログインしました: {bot.user}")

#ボイスチャンネル接続
@bot.command()
async def join(ctx):
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

#ボイスチャンネル退出
@bot.command()
async def leave(ctx):
    global active_text_channel
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        active_text_channel = None
        await ctx.send("切断しました！─=≡Σ((( つ•̀ω•́)つ")
    else:
        await ctx.send("Botはボイスチャンネルに接続していません。")

#再生中の音声を停止
@bot.command()
async def vstop(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        global is_audio_playing
        is_audio_playing = False
        await ctx.send("再生を停止しました！")
    else:
        await ctx.send("再生中の音声がありません。")

#コマンド実行者のキャラクターを設定
@bot.command()
async def set(ctx, character_name: str):
    global user_character_map

    if character_name not in CHARACTER_MAP:
        await ctx.send(f"キャラクター名 '{character_name}' は存在しません。有効なキャラクターを指定/config.jsonを確認してください。")
        return

    user_character_map[ctx.author.id] = CHARACTER_MAP[character_name]
    await ctx.send(f"キャラクターを '{character_name}' に設定しました！")

#辞書登録機能
@bot.command()
async def add(ctx, surface: str, pronunciation: str):
    guild_id = ctx.guild.id
    if guild_id not in server_dictionaries:
        server_dictionaries[guild_id] = []

    entry = {
        "surface": surface,
        "pronunciation": pronunciation
    }
    with open("serverdata.json", "w", encoding="utf-8") as writejson1:
        json.dump(entry, writejson1, indent=4, ensure_ascii=False)
    server_dictionaries[guild_id].append(entry)
    await ctx.send(f"辞書に単語を登録しました: {surface} ({pronunciation})")

#音声ファイルの再生設定を変更
@bot.command()
async def audioplay(ctx, state: str):
    guild_id = ctx.guild.id
    if state.lower() not in ["true", "false"]:
        await ctx.send("無効な設定です。有効な値: true または false")
        return

    server_audio_playback_settings[guild_id] = state.lower() == "true"
    status = "有効" if server_audio_playback_settings[guild_id] else "無効"
    await ctx.send(f"音声ファイルの再生設定を{status}にしました！")

#録音を開始
@bot.command()
async def rec(ctx):
    if ctx.voice_client and isinstance(ctx.voice_client, AudioRecorder):
        ctx.voice_client.recording = True
        await ctx.send("録音を開始しました！")
    else:
        await ctx.send("ボイスチャンネルに接続していません！")

#録音を終了
@bot.command()
async def rstop(ctx):
    if ctx.voice_client and isinstance(ctx.voice_client, AudioRecorder):
        ctx.voice_client.recording = False
        ctx.voice_client.write_audio_files()
        await ctx.send("録音を停止し、ファイルを保存しました！")
    else:
        await ctx.send("録音を開始していません！")

#録音データ出力
@bot.command()
async def send_audio(ctx, display_name: str, mode: str = "divided"):
    channel = bot.get_channel(OUTPUT_CHANNELID)
    if not channel:
        await ctx.send("出力先のチャンネルが見つかりません。config.jsonを確認してください。")
        return
    
    if display_name.lower() == "all":
        if user_audio:
            if mode == "divided":
                for display_name, file_path in user_audio.items():
                    await channel.send(f"{display_name} の録音:", file=discord.File(file_path))
            elif mode == "merged":
                combined = AudioSegment.silent(duration=1000)
                for file_path in user_audio.values():
                    audio = AudioSegment.from_mp3(file_path)
                    combined += audio
                merged_path = os.path.join(SAVE_DIR, "merged_audio.mp3")
                combined.export(merged_path, format="mp3")
                await channel.send("全員の録音を結合しました！", file=discord.File(merged_path))
            else:
                await channel.send("無効なモードです。'divided' または 'merged' を指定してください。")
        else:
            await channel.send("録音データがありません。")
    elif display_name in user_audio:
        await channel.send(file=discord.File(user_audio[display_name]))
    else:
        await channel.send("録音データがありません。")

#録音データ削除
@bot.command()
async def recdelete(ctx):
    await ctx.send("本当にすべての録音データを削除しますか？ `y/n`")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["y", "n"]
    
    try:
        msg = await bot.wait_for("message", check=check, timeout=30)
        if msg.content.lower() == "y":
            for file in os.listdir(SAVE_DIR):
                file_path = os.path.join(SAVE_DIR, file)
                os.remove(file_path)
            user_audio.clear()
            await ctx.send("すべての録音データを削除しました。")
        else:
            await ctx.send("録音データの削除をキャンセルしました。")
    except asyncio.TimeoutError:
        await ctx.send("タイムアウトしました。録音データの削除をキャンセルします。")

#コマンドの使用方法を表示
@bot.command()
async def help(ctx):
    help_message = """
    **使用可能なコマンド一覧**:
    `!join`: ボイスチャンネルに接続

    `!leave`: ボイスチャンネルから切断

    `!vstop`: 再生中の音声を停止

    `!set <キャラクター名>`: あなたのキャラクターを設定

    `!add <単語> <読み>`: サーバー固有の辞書に単語を登録

    `!audioplay <true|false>`: 添付された音声ファイルの再生設定を変更
        true: 再生する
        false: 再生しない

    `!rec`: ボイスチャンネルの録音を開始

    `!rstop`: ボイスチャンネルの録音を停止

    `!sendaudio <ユーザー表示名>`: 特定のユーザーの録音した音声を出力

    `!sendaudio all <divided|merged>`: 全員分の録音した音声を出力
        divided: 各ユーザーごとに分ける
        merged: 1つのファイルにまとめる

    `!recdelete`: 録音データを削除

    `!help`: このヘルプを表示
    """
    await ctx.send(help_message)

#メッセージ読み上げ処理
@bot.event
async def on_message(message):
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
                        tts_text = "音声添付"
                        await generate_and_play_tts(message.guild.voice_client, tts_text, character_id)
                else:
                    tts_text = f"{file_type}添付"
                    await generate_and_play_tts(message.guild.voice_client, tts_text, character_id)
        elif any(word.startswith("http") for word in message.content.split()):
            await generate_and_play_tts(message.guild.voice_client, "リンク省略", character_id)
        else:
            processed_text = apply_custom_dictionary(guild_id, message.content)
            await generate_and_play_tts(message.guild.voice_client, processed_text, character_id)

#VOICEVOXを使ってTTSを生成し再生
async def generate_and_play_tts(voice_client, text, character_id):
    global is_audio_playing
    try:
        encoded_text = urllib.parse.quote(text)
        query_url = f"http://localhost:50021/audio_query?text={encoded_text}&speaker={character_id}"
        query_response = requests.post(query_url)
        query_response.raise_for_status()
        audio_query = query_response.json()

        synthesis_response = requests.post(f"http://localhost:50021/synthesis", params={"speaker": character_id}, json=audio_query)
        synthesis_response.raise_for_status()

        audio_data = BytesIO(synthesis_response.content)

        if not is_audio_playing or not voice_client.is_playing():
            is_audio_playing = True
            voice_client.play(discord.FFmpegPCMAudio(audio_data, pipe=True, executable="ffmpeg.exe"), after=lambda e: print(f"再生終了: {e}"))
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

#添付された音声をURLから再生
async def play_audio_from_url(voice_client, url):
    global is_audio_playing
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        audio_data = BytesIO(response.content)

        if not is_audio_playing:
            is_audio_playing = True
            voice_client.play(discord.FFmpegPCMAudio(audio_data, pipe=True, executable="ffmpeg.exe"), after=lambda e: print(f"再生終了: {e}"))
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

#録音データを保存する辞書(なにこれ?)
user_audio = {}
recording = False

class AudioRecorder(discord.VoiceClient):
    def __init__(self, client, channel):
        super().__init__(client, channel)
        self.buffer = {}
        self.recording = False

    async def recv_audio(self, user, data):
        if self.recording:
            display_name = user.display_name
            if display_name not in self.buffer:
                self.buffer[display_name] = []
            self.buffer[display_name].append(np.frombuffer(data, dtype=np.int16))

    def write_audio_files(self):
        if not os.path.exists(SAVE_DIR):
            os.makedirs(SAVE_DIR)
        for display_name, data in self.buffer.items():
            audio_data = np.concatenate(data, axis=0)
            file_path = os.path.join(SAVE_DIR, f"{display_name}.wav")
            audio = AudioSegment(audio_data.tobytes(), frame_rate=48000, sample_width=2, channels=1)
            audio.export(file_path, format="wav")
            mp3_path = file_path.replace(".wav", ".mp3")
            audio.export(mp3_path, format="mp3")
            os.remove(file_path)
            user_audio[display_name] = mp3_path

bot.run(TOKEN)
