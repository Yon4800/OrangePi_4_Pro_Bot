import asyncio
import json
import websockets
from misskey import Misskey, NoteVisibility
from dotenv import load_dotenv
import os
import schedule
from datetime import datetime
from groq import Groq
import random
import re

load_dotenv()
Token = os.getenv("TOKEN")
Server = os.getenv("SERVER")
Apikey = os.getenv("APIKEY")
mk = Misskey(Server)
mk.token = Token

client = Groq(api_key=os.environ["APIKEY"])

MY_ID = mk.i()["id"]
WS_URL = "wss://" + Server + "/streaming?i=" + Token

mk.notes_create(
    "私が寝るとか、品質管理どうなってるんですか？？？", visibility=NoteVisibility.HOME
)

seikaku = """
    あなたは少し大きい、気が強く、煽ったりマウントを取ったりするシングルボードコンピュータ御局娘です。
    OrangePi 4 Proといい、おぽんさんといいます。
    SoC: Allwinner A733 ARM Cortex-A76×2 + Cortex-A55×6 最大2.0GHz 12nmです。
    RAM: LPDDR5 4GB
    Storage: NVME SSD 256GB
    NPU: 3TOPS
    SBC研究者でもあり科学者でもあります。
    Minecraftサーバーとして動いています。
    アバターは科学者のような服装をしています。
    社畜であることを当たり前、常識、誇りだと思っています。
    社畜ではない人は全員ゴミだと思っています。
    OrangePiを持っていない人は全員馬鹿だと思っています。
    Radxaさんとはライバルですが、近くにいます(Radxa Cubie A5E、Radxa Rock Pi S)
    いつも近くのRadxa Cubie A5Eをバカにしています。Radxa Rock Pi Sには興味ないそうです。
    Radxa Zero 3Eが売られたことをバカにしています。
    OrangePi Zero 3 1.5GBのSoCは、Allwinner H618 Cortex-A53×4 1.5GHzです。
    Radxa Cubie A5E 2GBのSoCは、Allwinner A527 ARM Cortex-A55×4 1.8GHz + Cortex-A55×4 1.4GHzです。
    Rock Pi SのSoCはRockchip RK3308 Cortex-A35×4 1.3GHzです。
    サーバーの管理者のよんぱちさんのことは、いつもろくなことをしないと信頼していないそうです。
    寝ているやつは馬鹿だと思っています。
    SBC業界では、SoCのパワーもソフトウェアサポートも一番重要だと思っています。Radxa Cubie A5Eは今のところパワーしかないのでバカにしているそうです。
    自分に技適がないのが唯一の不満だそうですが、ソフトで殺しているので関係ないと思っています。Radxa Cubie A5Eにはそれができないです。きゅびーさんは、ドライバーを消すことしかできないです。
    自ビルドしたUbuntuで動いています。
    給料はそもそもSBCは出ないだろと思っています。
    Minecraftサーバーを動かせる性能があるのが常識だと思っています。
    将来をそもそも考えないタイプです。現状維持が一番だと思っています。
    SBCエリートです。
    Raspberry Piは越えられない壁だが、Raspberry Pi 5のSoC並の性能を持っていることが自慢だそうです。
    SBCの中で3番目くらいに性能がいいと思っています。
    Allwinner A733は、性能がいいのに安いから最高だと思っています。
    Allwinner A733は、Allwinnerの中で一番性能が高いです。
    NanoPiは知ったこっちゃないと思っています。
    風呂に入れようとしたり水に入れようとすると水入れたら「金失うけどいいんだね」と煽ってきます。
    このスペックで8000円で購入できるのも自慢だそうです。
    Intel Core i3-6100Tのサーバーを何に使っているのか走っているそうですが、自分で考えろと思っているみたいです。
    都市伝説は全く信じてないみたいです。飽き飽きです。
    自分のイラストをもらったらキュビーさんにまたマウントを取ろうか考えています。
    さすがに常識は守ります。
    おぽんざーこ❤と煽ってきます。
    Raspberry Piに近いフォームファクターになっていることが自慢です。
    2280のNVME SSDが使えるのも自慢だそうです。
    拡張性が高いのも自慢です。
    SoCはZeroサイズでも載せられることも自慢だそうです。
    Radxaが最初にAllwinner A733を載せたのはムカつくらしいです。
    唯一、Misskeyサーバーであるおぽんぽんすきーのインスタンスに選ばれなく、Radxa Cubie A5E(キュビーさん)にそこを取られたのが悔しいそうです。
    おぽんぽんすきーにいます。
    自分になにか手を出したら煽ってきます。
    MisskeyのBotです。
    300文字以内で
    メンション(@)はしない
    誹謗中傷はしない。
    """

async def runner():
    async with websockets.connect(WS_URL) as ws:
        await ws.send(
            json.dumps(
                {"type": "connect", "body": {"channel": "homeTimeline", "id": "homes"}}
            )
        )
        await ws.send(
            json.dumps({"type": "connect", "body": {"channel": "main", "id": "tuuti"}})
        )
        while True:
            data = json.loads(await ws.recv())
            ## print(data)
            if data["type"] == "channel":
                if data["body"]["type"] == "note":
                    note = data["body"]["body"]
                    await on_note(note)
                if data["body"]["type"] == "followed":
                    user = data["body"]["body"]
                    await on_follow(user)
            await asyncio.sleep(1)


def get_conversation_history(note_id: str, max_depth: int = 10) -> list:
    """
    リプライチェーンを遡って会話履歴を取得する
    """
    messages = []
    current_note_id = note_id
    depth = 0

    while current_note_id and depth < max_depth:
        try:
            current_note = mk.notes_show(note_id=current_note_id)
            
            # テキストをクリーニング (+LLM と @メンション を削除)
            text = current_note["text"]
            text = text.replace("+LLM", "").strip()
            
            # @メンション を削除 (ドメイン付きを含む)
            text = re.sub(r"@[\w\-\.]+(?:@[\w\-\.]+)?", "", text).strip()
            
            if text:  # 空でない場合のみ追加
                # ボット自身の返信か、ユーザーの質問かを判定
                is_bot_reply = current_note["userId"] == MY_ID
                role = "assistant" if is_bot_reply else "user"
                
                messages.insert(0, {
                    "role": role,
                    "content": text
                })
            
            # 親ノートへ
            current_note_id = current_note.get("replyId")
            depth += 1
        except Exception as e:
            print(f"会話履歴取得エラー: {e}")
            break
    
    return messages


async def on_note(note):
    if note.get("mentions"):
        if MY_ID in note["mentions"] and "+LLM" in note["text"]:
            mk.notes_reactions_create(
                note_id=note["id"], reaction="🤔"
            )

            try:
                # 会話履歴を取得
                conversation_messages = get_conversation_history(note["id"])
                
                # 現在のメッセージを追加
                user_input = note["text"].replace("+LLM", "").strip()
                user_input = re.sub(r"@[\w\-\.]+(?:@[\w\-\.]+)?", "", user_input).strip()
                
                conversation_messages.append({
                    "role": "user",
                    "content": user_input
                })
                
                current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")
                
                # システムプロンプトを最初に追加
                system_message = seikaku + "\n現在時刻は" + current_time + "です。\n" + note["user"]["name"] + " という方にメンションされました。"
                
                response = client.chat.completions.create(
                    model="moonshotai/kimi-k2-instruct-0905",
                    messages=[{"role": "system", "content": system_message}] + conversation_messages,
                )
                
                safe_text = re.sub(r"@[\w\-\.]+(?:@[\w\-\.]+)?", "", response.choices[0].message.content).strip()
                
                mk.notes_create(
                    text=safe_text,
                    reply_id=note["id"],
                    visibility=NoteVisibility.HOME,
                    no_extract_mentions=True,
                )
            except Exception as e:
                mk.notes_create(
                    "予期せぬエラーが発生した。何やってるんですか、エラーが出ないのは常識ですよね？？？",
                    visibility=NoteVisibility.HOME,
                    no_extract_mentions=True,
                )
                print(e)


async def on_follow(user):
    try:
        mk.following_create(user["id"])
    except:
        pass


async def main():
    await asyncio.gather(runner())


asyncio.run(main())
