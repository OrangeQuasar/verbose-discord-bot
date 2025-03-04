# verbose-discord-bot
 this bot provides various functions regarding voice channels

The bot is currently being developed and has been tested on python version 1.13.1. After editing `settings.json`, run `openwalkbot.py` to run the bot.
==================================================================================================================================================

日本語版のREADME.mdは気が向いたら用意します。頑張って英語を読んでください。
-----------------------------------------------------------------------------------------------------------

We are currently confirming an issue where the following functions are not working properly. We plan to fix this issue as soon as possible.
===========================================================================================================================================
* Some settings are not saved.
* `!output merge` causes discrepancies in each user's audio
* When mentioning a user or channel, their ID will be read out loud.

Functions in voice channel
==========================
*These are in the development stage and are subject to change. New features will continue to be added in the future as long as the author remains motivated.
-------------------------------------------------------------------------------------------------------------------------------------------------------------
* Read out the sent message with VOICEVOX (VOICEVOX server, dictionary registration, character change & addition possible)
* Identifies attached files by image, video, document, audio, etc. and reads "XX file attached". For audio files, there is a function to play them during a call (can be changed in settings)
* Record calls and output in mp3 format to specified text channel (output per user / recordings of all users can be combined into one)
* Reminder function that allows you to specify date and time, interval, and target users

List of available commands
==========================
*These are in the development stage and are subject to change.
--------------------------------------------------------------
* `!join`: join a voice channel
* `!leave`: disconnect from a voice channel
* `!vstop`: stop audio currently playing
* `!set <character name>`: set the character who will read the executor's message
* `!add <word> <reading>`: register a word to the dictionary
* `!deldic`: remove a word in the dictionary
* `!audioplay`: change the playback settings for attached audio files (true: play, false: don't play)
* `!rec`: start recording a voice channel
* `!recstop`: stop recording a voice channel
* `!output <<user display name>|all|merge>`: output recorded audio (user display name: output a specific user's recorded audio, all: output all users' recorded audio, merge: output all users' recorded audio combined into one)
* `!reminder yyyy-mm-dd-hh-mm <interval (min)> <user name>`: Reminder at a specified time
* `!remstop`: Cancel reminder
* `!help`: Show this help
