# verbose-discord-bot
 this bot provides various functions regarding voice channels

Currently I am preparing English README.md
==========================================

現在辞書登録機能が正常に機能しないこと・読み上げ中にメッセージ等送信でエラーが発生することを確認しています。早急に修正を行う予定です。
===================================================================

ボイスチャンネルでの機能
============

※これらは開発段階におけるものであり、変更される可能性があります。また作者のやる気が続く限り今後も新機能が追加されていく予定です。
-----------------------------------------------------------------

原則以下の機能は\`!join\`コマンドが送信されたテキストチャンネル下て動作します。

*   送信されたメッセージをVOICEVOXで読み上げる(辞書登録・キャラクター変更・追加可能)
*   添付されたファイルを画像、動画、ドキュメント、音声、その他で判別し、「〇〇ファイル添付」と読み上げる。音声ファイルの場合は通話内で再生する機能あり(設定で変更可)。
*   【新機能】通話を録音し、指定したテキストチャンネルにmp3形式で出力(ユーザーごとの出力・全ユーザーの録音を1つに結合可)。

使用可能なコマンド一覧
===========

※これらは開発段階におけるものであり、変更される可能性があります。
---------------------------------

原則以下の機能は\`!join\`コマンドが送信されたテキストチャンネル下て動作します。

*   \`!join\`: ボイスチャンネルに接続
*   \`!leave\`: ボイスチャンネルから切断
*   \`!vstop\`: 再生中の音声を停止
*   \`!set <キャラクター名>\`: 実行者のメッセージを読み上げるキャラクターを設定
*   \`!add <単語> <読み>\`: サーバー固有の辞書に単語を登録
*   \`!audioplay \`: 添付された音声ファイルの再生設定を変更(true: 再生する、false: 再生しない)
*   \`!rec\`: ボイスチャンネルの録音を開始
*   \`!rstop\`: ボイスチャンネルの録音を停止
*   \`!output <<ユーザー表示名>|all|merge>\`: 録音した音声を出力(ユーザー表示名: 特定のユーザーの録音音声を出力、all: 全ユーザーの録音音声を出力、merge: 全ユーザーの録音音声を1つにまとめて出力)
*   \`!help\`: このヘルプを表示
