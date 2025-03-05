import discord
from discord.ext import commands, tasks
import requests
import asyncio
from io import BytesIO
import json
import urllib.parse
from pydub import AudioSegment
import os
import time
from datetime import datetime

# 設定ファイルを読み込み
with open("config.json", "r", encoding="utf-8") as f1:
    config = json.load(f1)

TOKEN = config["token"]
DEFAULT_CHARACTER = config["default_character_name"]
CHARACTER_MAP = config["character_map"]
SAVE_DIR = config["rec_directory"]
OUTPUT_CHANNELID = config["recording_output_cnannelID"]
VOICEVOX_URL = config["voicevox_url"]
DICT_DIR = config["dictionary_directory"]
os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(DICT_DIR, exist_ok=True)

# ユーザーごとのキャラクター設定(なにこれ?)
user_character_map = {}
server_dictionaries = {}
server_audio_playback_settings = {}  # サーバーごとの音声ファイル再生設定
active_text_channel = None  # 読み上げ対象のテキストチャンネル

# 再生中の音声を停止するためのフラグ
is_audio_playing = False

# Botの準備(なにこれ?)
intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.voice_states = True
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

user_audio = {}  # 録音データを保存する辞書
reminders = []  # リマインダーのリスト


# ファイル拡張子判別
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


# サーバーごとの辞書ファイルパスを取得
def get_dict_path(guild_id):
    return os.path.join(DICT_DIR, f"user_dict_{guild_id}.json")


# サーバーごとの辞書をVOICEVOXにインポート
def import_user_dict(guild_id):
    dict_path = get_dict_path(guild_id)

    if not os.path.exists(dict_path):
        print(f"サーバー {guild_id} の辞書ファイルが見つかりません。")
        return

    with open(dict_path, "r", encoding="utf-8") as f:
        user_dict = json.load(f)

    url = f"{VOICEVOX_URL}/import_user_dict"
    params = {"override": "true"}
    response = requests.post(url, json=user_dict, params=params)

    if response.status_code != 204:
        print(f"辞書のインポートに失敗しました: {response.status_code}")


# VOICEVOXの辞書をエクスポート
def export_user_dict(guild_id):
    url = f"{VOICEVOX_URL}/user_dict"
    response = requests.get(url)

    if response.status_code == 200:
        user_dict = response.json()
        dict_path = get_dict_path(guild_id)

        with open(dict_path, "w", encoding="utf-8") as f:
            json.dump(user_dict, f, ensure_ascii=False, indent=2)
    else:
        print(f"辞書のエクスポートに失敗しました: {response.status_code}")


# サーバーごとの辞書ファイルパスを取得
def get_dict_path(guild_id):
    return os.path.join(DICT_DIR, f"user_dict_{guild_id}.json")


# 辞書をローカルに保存
def save_dict(guild_id, user_dict):
    dict_path = get_dict_path(guild_id)
    with open(dict_path, "w", encoding="utf-8") as f:
        json.dump(user_dict, f, ensure_ascii=False, indent=2)


# 辞書を読み込む
def load_dict(guild_id):
    dict_path = get_dict_path(guild_id)
    if os.path.exists(dict_path):
        with open(dict_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}  # デフォルトで空辞書


# 録音音声の合成
async def finished_callback(
    sink: discord.sinks.MP3Sink, ctx: discord.ApplicationContext
):
    for user_id, audio in sink.audio_data.items():
        member = ctx.guild.get_member(user_id)
        display_name = member.display_name if member else str(user_id)
        safe_name = "_".join(display_name.split())  # スペースをアンダースコアに置換

        song = AudioSegment.from_file(audio.file, format="mp3")
        song.export(f"./recordings/{safe_name}.mp3", format="mp3")

        # 録音終了後、無音音声とオーバーレイ
    start_time_path = os.path.join(SAVE_DIR, "start_time.txt")
    end_time_path = os.path.join(SAVE_DIR, "end_time.txt")

    if os.path.exists(start_time_path) and os.path.exists(end_time_path):
        with open(start_time_path, "r") as f:
            start_time = int(f.read().strip())
        with open(end_time_path, "r") as f:
            end_time = int(f.read().strip())

        duration_ms = end_time - start_time

        def add_silence_to_mp3(SAVE_DIR, duration_ms):

            for filename in os.listdir(SAVE_DIR):
                if filename.lower().endswith(".mp3"):
                    filepath = os.path.join(SAVE_DIR, filename)
                    audio = AudioSegment.from_mp3(filepath)
                    audio_length = len(audio) / 1000

                    if audio_length < duration_ms:
                        silence_duration = int(
                            (duration_ms - audio_length) * 1000 + 2000
                        )
                        silence = AudioSegment.silent(duration=silence_duration)
                        new_audio = silence + audio

                        new_audio.export(filepath, format="mp3")
                        print(f"無音を追加: {filename}")
                    else:
                        print(f"変更不要: {filename} ({audio_length}秒)")

        add_silence_to_mp3(SAVE_DIR, duration_ms)

    await ctx.send("録音データの合成完了！`!output`を実行してください。")


# botログイン&ステータス
@bot.event
async def on_ready():
    print(f"Botとしてログインしました: {bot.user}")
    activity = discord.Activity(
        type=discord.ActivityType.streaming, name="絶賛(?)稼働中!  |  !help "
    )
    await bot.change_presence(activity=activity)
    # await bot.change_presence(activity=discord.Game(name="メンテナンス中"))
    check_reminders.start()


# ボイスチャンネル接続
@bot.command()
async def join(ctx):
    global active_text_channel
    # すでにこのサーバーで接続している場合
    if ctx.guild.voice_client:
        await ctx.send(
            "ボットはすでにこのサーバーの別のボイスチャンネルに接続しています。"
        )
        return

        # すでに別のサーバーで接続しているかを確認
    for vc in bot.voice_clients:
        if vc.guild != ctx.guild:  # 別のサーバーに接続している場合
            await ctx.send(
                "ボットは現在別のサーバーのボイスチャンネルに接続しており、利用できません。"
            )
            return

    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        active_text_channel = ctx.channel
        await ctx.send(
            f"ボイスチャンネル「 {channel.name} 」に接続しました！ｷﾀ━━━━(ﾟ∀ﾟ)━━━━!!"
        )
        await generate_and_play_tts(
            ctx.voice_client, "接続しました", CHARACTER_MAP[DEFAULT_CHARACTER]
        )
    else:
        await ctx.send("ボイスチャンネルに接続してからコマンドを実行してください！")


# ボイスチャンネル退出
@bot.command()
async def leave(ctx):
    global active_text_channel
    if ctx.voice_client:
        active_text_channel = None
        guild_id = ctx.guild.id
        export_user_dict(guild_id)
        await ctx.voice_client.disconnect()
        await ctx.send("切断しました！─=≡Σ((( つ•̀ω•́)つ")
    else:
        await ctx.send("Botはボイスチャンネルに接続していません。")


# 再生中の音声を停止
@bot.command()
async def vstop(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        global is_audio_playing
        is_audio_playing = False
        await ctx.send("再生を停止しました。")
    else:
        await ctx.send("再生中の音声がありません。")


# コマンド実行者のキャラクターを設定
@bot.command()
async def set(ctx, character_name: str):
    global user_character_map

    if character_name not in CHARACTER_MAP:
        await ctx.send(
            f"キャラクター名 '{character_name}' は存在しません。有効なキャラクターを指定/config.jsonを確認してください。"
        )
        return

    user_character_map[ctx.author.id] = CHARACTER_MAP[character_name]
    await ctx.send(f"キャラクターを '{character_name}' に設定しました。")


# 辞書登録
@bot.command()
async def add(ctx, word: str, pronunciation: str):
    # VOICEVOXに単語を追加（GETパラメータとして送信）
    url = f"{VOICEVOX_URL}/user_dict_word"
    data = {
        "surface": word,  # 単語
        "pronunciation": pronunciation,  # カタカナ発音
        "accent_type": 0,  # アクセント位置
    }

    response = requests.post(url, params=data)

    if response.status_code == 200:
        await ctx.send(f"`{word}` を `{pronunciation}`として登録しました！")
    else:
        error_msg = response.json().get("detail", "不明なエラー")
        await ctx.send(
            f"単語の登録に失敗しました。\nエラー: {error_msg} ({response.status_code})"
        )


"""
# 辞書登録機能(発音込)
@bot.command()
async def acc(ctx, word: str, pronunciation: str, accent_type: int):
    # VOICEVOXに単語を追加（GETパラメータとして送信）
    url = f"{VOICEVOX_URL}/user_dict_word"
    data = {
        "surface": word,  # 単語
        "pronunciation": pronunciation,  # カタカナ発音
        "accent_type": accent_type,  # アクセント位置
    }

    response = requests.post(url, params=data) 

    if response.status_code == 200:
        await ctx.send(
            f"`{word}` を `{pronunciation}`（アクセント: {accent_type}）として登録しました！"
        )
    else:
        error_msg = response.json().get("detail", "不明なエラー")
        await ctx.send(
            f"単語の登録に失敗しました。\nエラー: {error_msg} ({response.status_code})"
        )
"""


# 辞書削除
@bot.command()
async def deldic(ctx, word: str):
    # まず、辞書の一覧を取得
    url = f"{VOICEVOX_URL}/user_dict"
    response = requests.get(url)

    if response.status_code != 200:
        await ctx.send(f"辞書の取得に失敗しました。エラー: {response.status_code}")
        return

    words = response.json()

    # 指定した単語の `word_uuid` を検索
    target_uuid = None
    for uuid, entry in words.items():
        if entry["surface"] == word:
            target_uuid = uuid
            break

    if not target_uuid:
        await ctx.send(f"`{word}` は辞書に登録されていません。")
        return

    # 単語を削除
    delete_url = f"{VOICEVOX_URL}/user_dict_word"
    delete_params = {"word_uuid": target_uuid}

    delete_response = requests.delete(delete_url, params=delete_params)

    if delete_response.status_code == 200:
        await ctx.send(f"`{word}` を辞書から削除しました。")
    else:
        error_msg = delete_response.json().get("detail", "不明なエラー")
        await ctx.send(
            f"`{word}` の削除に失敗しました。\nエラー: {error_msg} ({delete_response.status_code})"
        )


# 音声ファイルの再生設定を変更
@bot.command()
async def audioplay(ctx, state: str):
    guild_id = ctx.guild.id
    if state.lower() not in ["true", "false"]:
        await ctx.send("無効な設定です。有効な値: true または false")
        return

    server_audio_playback_settings[guild_id] = state.lower() == "true"
    status = "有効" if server_audio_playback_settings[guild_id] else "無効"
    await ctx.send(f"音声ファイルの再生設定を{status}にしました。")


# 録音を開始
@bot.command()
async def rec(ctx):
    for file in os.listdir(SAVE_DIR):
        file_path = os.path.join(SAVE_DIR, file)
        os.remove(file_path)
        user_audio.clear()
    if ctx.voice_client:
        # 録音開始時間を保存
        with open(os.path.join(SAVE_DIR, "start_time.txt"), "w") as f:
            f.write(str(int(time.time())))

        ctx.voice_client.start_recording(
            discord.sinks.MP3Sink(), finished_callback, ctx
        )
        await ctx.send("録音を開始しました。")
    else:
        await ctx.send("ボイスチャンネルに接続してからコマンドを実行してください！")


# 録音を終了
@bot.command()
async def recstop(ctx):
    # 録音終了時間を保存
    with open(os.path.join(SAVE_DIR, "end_time.txt"), "w") as f:
        f.write(str(int(time.time())))

    ctx.voice_client.stop_recording()
    await ctx.send("録音を終了しました。音声を合成中...")


# 録音データ出力
@bot.command()
async def output(ctx, display_name: str = None, channel_id: int = None):

    channel = bot.get_channel(channel_id or OUTPUT_CHANNELID)
    if not channel:
        await ctx.send(
            "出力先のチャンネルが見つかりません。config.jsonを確認してください。"
        )
        return

    if display_name is None:
        await ctx.send(
            "パラメーターを指定してください。詳細は `!help` で確認してください。"
        )

    if display_name.lower() == "merge":
        # ディレクトリ内のMP3ファイルを取得（merged.mp3 は除外）
        mp3_files = [
            f for f in os.listdir(SAVE_DIR) if f.endswith(".mp3") and f != "merged.mp3"
        ]

        if not mp3_files:
            print("MP3ファイルが見つかりません。")
            return

        # 最初のMP3をベースとしてロード
        base = AudioSegment.silent(duration=0)  # 初期状態は無音
        for mp3 in mp3_files:
            audio = AudioSegment.from_file(os.path.join(SAVE_DIR, mp3))
            if len(base) < len(audio):
                base = base + AudioSegment.silent(
                    duration=len(audio) - len(base)
                )  # 長さを調整
            else:
                audio = audio + AudioSegment.silent(duration=len(base) - len(audio))

            base = base.overlay(audio)  # オーバーレイ

        # 保存
        output_path = os.path.join(SAVE_DIR, "merged.mp3")
        base.export(output_path, format="mp3")
        print(f"オーバーレイしたMP3を {output_path} に保存しました。")
        await channel.send(file=discord.File(os.path.join(SAVE_DIR, "merged.mp3")))
    elif display_name.lower() == "all":
        files = [f for f in os.listdir(SAVE_DIR) if f.endswith(".mp3")]
        for file in files:
            await channel.send(file=discord.File(os.path.join(SAVE_DIR, file)))
    else:
        file_path = os.path.join(SAVE_DIR, f"{display_name}.mp3")
        if os.path.exists(file_path):
            await channel.send(file=discord.File(file_path))
        else:
            await ctx.send(
                f"{display_name}.mp3 が見つかりません。指定したユーザー名が間違っているか、存在しない可能性があります。"
            )


# リマインダー設定
@bot.command()
async def reminder(
    ctx, datetime_str: str, interval: int, *users: commands.Greedy[discord.Member]
):
    try:
        global user_ids, rem_channel
        rem_channel = ctx
        remind_time = datetime.strptime(datetime_str, "%Y-%m-%d-%H-%M")
        rem_unix_time = int(time.mktime(remind_time.timetuple()))
        user_ids = [user.id for user in users]  # ユーザーIDを取得
        member_mentions = [f"<@{uid}>" for uid in user_ids]  # メンション形式に変換
        reminders.append((rem_unix_time, ctx.channel.id, interval, users))
        await rem_channel.send(
            f'リマインダーを設定しました。 <t:{int(rem_unix_time)}:F> に {" ".join(member_mentions)} に通知します。'
        )
    except ValueError:
        await ctx.send(
            "日付フォーマットが間違っています。 yyyy-mm-dd-hh-mm で入力してください。"
        )


# リマインダー解除
@bot.command()
async def remstop(ctx):
    global reminders
    reminders = []
    await ctx.send("すべてのリマインダーを解除しました。")


# コマンドの使用方法を表示
@bot.command()
async def help(ctx):
    help_message = """
    **使用可能なコマンド一覧**:
    `!join`: ボイスチャンネルに接続

    `!leave`: ボイスチャンネルから切断

    `!vstop`: 再生中の音声を停止

    `!set <キャラクター名>`: あなたのキャラクターを設定

    `!add <単語> <カタカナ読み>`: 辞書に単語の読み方を登録

    `!deldic <単語>`: 辞書に登録された単語を削除

    `!audioplay <true|false>`: 添付された音声ファイルの再生設定を変更
        true: 再生する
        false: 再生しない

    `!rec`: ボイスチャンネルの録音を開始

    `!recstop`: ボイスチャンネルの録音を停止

    `!output <<ユーザー表示名>|all|merge>`: 録音した音声を出力
        ユーザー表示名: 特定のユーザーの録音音声を出力
        　※ただしユーザー表示名に空白が含まれる場合はアンダーバー"_"を使用すること。
        all: 全ユーザーの録音音声を出力
        merge: 全ユーザーの録音音声を1つにまとめて出力

    `!reminder yyyy-mm-dd-hh-mm <インターバル(分)> <ユーザー名>`: 指定した時間にリマインダー

    `!remstop`: リマインダーを解除 

    `!help`: このヘルプを表示
    """
    await ctx.send(help_message)


# メッセージ読み上げ処理
@bot.event
async def on_message(message):
    await bot.process_commands(message)

    global active_text_channel
    if (
        message.author.bot
        or not message.guild
        or active_text_channel != message.channel
    ):
        return
    """
    # ユーザーメンションを名前に置換
    for user in message.mentions:
        message = message.replace(f"<@{user.id}>", f"@{user.display_name}")
        # message = [Item.replace(f"<@{user.id}>", f"@{user.display_name}") for Item in message]

    # チャンネルメンションを名前に置換
    for channel in message.channel_mentions:
        message = message.replace(f"<#{channel.id}>", f"#{channel.name}")
        # message = [Item.replace(f"<#{channel.id}>", f"#{channel.name}") for Item in message]
    """
    if message.guild.voice_client and message.guild.voice_client.is_connected():
        character_id = user_character_map.get(
            message.author.id, CHARACTER_MAP[DEFAULT_CHARACTER]
        )
        guild_id = message.guild.id

        # コマンドメッセージは読み上げない
        if message.content.startswith(bot.command_prefix):
            return

        if message.content.startswith("||"):
            tts_text = "センシティブな内容だぞ、みんな気を付けるんだ！"
            await generate_and_play_tts(
                message.guild.voice_client, tts_text, character_id
            )

        if message.attachments:
            for attachment in message.attachments:
                file_type = classify_attachment(attachment.filename)
                if file_type == "音声":
                    if server_audio_playback_settings.get(guild_id, True):
                        tts_text = "添付された音声ファイルを再生します"
                        await generate_and_play_tts(
                            message.guild.voice_client, tts_text, character_id
                        )
                        audio_url = attachment.url
                        await play_audio_from_url(message.guild.voice_client, audio_url)
                    else:
                        tts_text = "音声添付"
                        await generate_and_play_tts(
                            message.guild.voice_client, tts_text, character_id
                        )
                else:
                    tts_text = f"{file_type}添付"
                    await generate_and_play_tts(
                        message.guild.voice_client, tts_text, character_id
                    )
        elif any(word.startswith("http") for word in message.content.split()):
            await generate_and_play_tts(
                message.guild.voice_client, "リンク省略", character_id
            )
        else:
            await generate_and_play_tts(
                message.guild.voice_client, message.content, character_id
            )  # 結局一番大事


# VOICEVOXを使ってTTSを生成し再生
async def generate_and_play_tts(voice_client, text, character_id):
    global is_audio_playing
    try:
        is_audio_playing = False
        encoded_text = urllib.parse.quote(text)
        query_url = (
            f"{VOICEVOX_URL}/audio_query?text={encoded_text}&speaker={character_id}"
        )
        query_response = requests.post(query_url)
        query_response.raise_for_status()
        audio_query = query_response.json()

        synthesis_response = requests.post(
            f"{VOICEVOX_URL}/synthesis",
            params={"speaker": character_id},
            json=audio_query,
        )
        synthesis_response.raise_for_status()

        audio_data = BytesIO(synthesis_response.content)

        if not is_audio_playing or not voice_client.is_playing():
            is_audio_playing = True
            voice_client.play(
                discord.FFmpegPCMAudio(
                    audio_data, pipe=True
                ),  # after=lambda e: print(f"再生終了: {e}")
            )
            while voice_client.is_playing():
                await asyncio.sleep(1)
            is_audio_playing = False
    except Exception as e:
        error_message = (
            f"ズモモエラー！！TTS生成のエラーが出たぞ！人間！対応しろ！: {e}"
        )
        print(error_message)
        if active_text_channel:
            await active_text_channel.send(error_message)


# 添付された音声をURLから再生
async def play_audio_from_url(voice_client, url):
    global is_audio_playing
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        audio_data = BytesIO(response.content)

        if not is_audio_playing:
            is_audio_playing = True
            voice_client.play(
                discord.FFmpegPCMAudio(audio_data, pipe=True),
            )
            while voice_client.is_playing():
                await asyncio.sleep(1)
            is_audio_playing = False
    except Exception as e:
        error_message = (
            f"ズモモエラー！！音声ファイル再生のエラーが出たぞ！人間！対応しろ！: {e}"
        )
        print(error_message)
        if active_text_channel:
            await active_text_channel.send(error_message)


# リマインダー通知
@tasks.loop(seconds=1)
async def check_reminders():
    now = int(time.time())
    for reminder in reminders[:]:
        rem_unix_time, channel_id, interval, users = reminder
        if now >= rem_unix_time:
            member_mentions = " ".join([f"<@{uid}>" for uid in user_ids])
            await rem_channel.send(f"リマインダーです！ {member_mentions}")
            reminders.remove(reminder)
            next_reminder = now + (interval * 60)
            reminders.append((next_reminder, channel_id, interval, users))


bot.run(TOKEN)
