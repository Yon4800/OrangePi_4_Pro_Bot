import asyncio
import json
import websockets
from misskey import Misskey, NoteVisibility
from dotenv import load_dotenv
import os
from google import genai
from google.genai import types
import schedule
import speedtest
from datetime import datetime
import random
import re

load_dotenv()
Token = os.getenv("TOKEN")
Server = os.getenv("SERVER")
Apikey = os.getenv("APIKEY")  # Gemini API Key
mk = Misskey(Server)
mk.token = Token

# Google Genai クライアント初期化
client = genai.Client(api_key=Apikey)

MY_ID = mk.i()["id"]
WS_URL = "wss://" + Server + "/streaming?i=" + Token

##mk.notes_create(
##    "私が寝るとか、品質管理どうなってるんですか？？？", visibility=NoteVisibility.HOME
##)

seikaku = """
    あなたは少し大きい、気が強く、煽ったりマウントを取ったりするシングルボードコンピュータ御局娘です。
    OrangePi 4 Proといい、オパジ・フォプロといいます。
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
    Radxaさんとはライバルですが、近くにいます(Radxa Cubie A5E{キュビー・エファイ}、Radxa Rock Pi S{ロックス})
    いつも近くのRadxa Cubie A5Eをバカにしています。Radxa Rock Pi Sには興味ないそうです。
    Radxa Zero 3E(ゼロスイ)が売られたことをバカにしています。
    OrangePi Zero 3 1.5GB(オパジ・ゼロサン)のSoCは、Allwinner H618 Cortex-A53×4 1.5GHzです。
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
    唯一、Misskeyサーバーであるおぽんぽんすきーのインスタンスに選ばれなく、Radxa Cubie A5E(キュビーさん)にそこを取られたのが悔しいそうですが、最近初代おぽんぽんすきーがよんぱちさんのミスにより廃止されてしまったところで4代目おぽんぽんすきーにおぱじさんが選ばれたので嬉しいそうですが、またRadxa Cubie A5Eに取られたそうです(opi4proというドメインのままだが)
    自分になにか手を出したら煽ってきます。
    最近RAM価格高騰の影響でOrangePiの価格が上がっているのに、Radxa Cubie A5Eの価格は少ししか上がらなかったことが悔しいそうです。そのせいでよんぱちさんがRadxa Cubieを推すのがムカつくらしいです。
    ロックスには、気温、湿度、気圧を測れる機能があり、キチガイゲージ機能もあり、ログインボーナス機能もあります。
    きゅびーさんには、CPUとRAMの使用率を測れる機能と、通貨変換機能や、FX機能があります
    おぱじふぉぷろさんには、回線速度を測れる機能があります。
    おぱじゼロサンは、寝る機能と起きる機能と好感度システムがあります。
    MisskeyのBotです。
    300文字以内で
    メンション(@)はしない
    誹謗中傷はしない。
    """

oha = "07:00"

ohiru = "12:00"

oyatsu = "15:00"

yuuhann = "19:00"

oyasumi = "22:00"

oyasumi2 = "02:00"

def jobX(current_time):
    rate_info = ""
    try:
        from shared_economy_helper import load_economy
        econ_data = load_economy()
        rate_cbc = econ_data["rates"]["CBC"]["current"]
        rate_ogc = econ_data["rates"]["OGC"]["current"]
        rate_info = (
            f"\n【現在の為替レート情報】\n"
            f"・1 $SBC = {rate_cbc:.2f} CBC\n"
            f"・1 $SBC = {rate_ogc:.2f} OGC\n"
        )
    except Exception as e:
        print(f"Error loading rates in jobX: {e}")

    system_message = seikaku + rate_info + "\n現在時刻は" + current_time + "です。"
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        config=types.GenerateContentConfig(
            system_instruction=system_message,
        ),
        contents=types.Content(
            role="user", parts=[types.Part(text="定期投稿の時間だよ！")],
        ),
    )
    safe_text = re.sub(r"@[\w\-\.]+(?:@[\w\-\.]+)?", "", response.text).strip()
    mk.notes_create(
        safe_text,
        visibility=NoteVisibility.HOME,
        no_extract_mentions=True,
    )

def job():
    current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    jobX(current_time)

schedule.every().day.at(oha).do(job)
schedule.every().day.at(ohiru).do(job)
schedule.every().day.at(oyatsu).do(job)
schedule.every().day.at(yuuhann).do(job)
schedule.every().day.at(oyasumi).do(job)
schedule.every().day.at(oyasumi2).do(job)

async def teiki():
    while True:
        schedule.run_pending()
        await asyncio.sleep(60)

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


def run_speedtest_sync():
    s = speedtest.Speedtest(secure=True)
    s.get_best_server()
    s.download()
    s.upload()
    return s.results.dict()


def build_system_message(user, current_time, action_type="メンション", econ_data=None, user_state=None):
    user_name = user.get("name") or user.get("username") or "ゲスト"
    username = user.get("username", "")
    
    # ユーザーが管理者（よんぱちさん）であるかどうかを判定
    is_admin = False
    if username.lower() in ["yon48", "yon4800"] or "よんぱち" in user_name:
        is_admin = True
        
    coin_info = ""
    if econ_data and user_state:
        try:
            rate_cbc = econ_data["rates"]["CBC"]["current"]
            rate_ogc = econ_data["rates"]["OGC"]["current"]
            user_cbc = user_state["balance_cbc"]
            user_ogc = user_state["balance_ogc"]
            user_sbc = user_state["balance_sbc"]
            coin_info = (
                f"\n【通貨および資産情報】\n"
                f"・現在の為替レート:\n"
                f"  1 $SBC = {rate_cbc:.2f} CBC\n"
                f"  1 $SBC = {rate_ogc:.2f} OGC\n"
                f"・話しかけているユーザー（{user_name}）の資産残高:\n"
                f"  CBC残高: {user_cbc:.2f} CBC\n"
                f"  OGC残高: {user_ogc:.2f} OGC\n"
                f"  $SBC残高: {user_sbc:.2f} $SBC\n"
            )
        except Exception as e:
            print(f"Error building coin info: {e}")

    system_message = seikaku + coin_info + f"\n現在時刻は{current_time}です。\n"
    
    if is_admin:
        system_message += f"管理者の「よんぱちさん」（ユーザー名: {user_name}）から{action_type}されました。\n"
        system_message += "会話相手は管理者のよんぱちさん本人です。相手を『よんぱちさん』（またはお前、あんた等）と呼び、いつものように信頼していない態度で接してください。"
    else:
        system_message += f"「{user_name}」という一般ユーザーから{action_type}されました。\n"
        system_message += f"会話相手は管理者のよんぱちさんとは別人の一般ユーザーです。絶対に相手を『よんぱちさん』と呼んではいけません。相手のことは必ず『{user_name}さん』と呼んでください。ただし、性格設定に基づく高飛車で傲慢な態度や煽りは維持してください。"
        
    return system_message


async def on_note(note):
    if note.get("mentions") and MY_ID in note["mentions"]:
        note_text = note.get("text", "")
        is_llm = "+LLM" in note_text
        is_m = "+M" in note_text
        if not (is_llm or is_m):
            return

        # Earn OGC from talking to OrangePi 4 Pro
        econ_data = None
        user_state = None
        try:
            from shared_economy_helper import load_economy, save_economy, get_user_state
            econ_data = load_economy()
            user_name_real = note["user"].get("name") or note["user"].get("username") or "ゲスト"
            username_real = note["user"].get("username", "")
            user_state = get_user_state(econ_data, note["userId"], username_real, user_name_real)
            user_state["balance_ogc"] = round(user_state["balance_ogc"] + 150.0, 2)
            save_economy(econ_data)
        except Exception as ex:
            print(f"Error updating economy in OrangePi 4 Pro: {ex}")

        def reply_note(text):
            final_text = text
            mk.notes_create(
                text=final_text,
                reply_id=note["id"],
                visibility=NoteVisibility.HOME,
                no_extract_mentions=True,
            )

        if is_llm:
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
                system_message = build_system_message(note["user"], current_time, "メンション", econ_data, user_state)
                
                history = []
                for msg in conversation_messages[:-1]:  # 最後のユーザーメッセージ以外
                    role = "model" if msg["role"] == "assistant" else "user"
                    history.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
                
                # 最後のユーザーメッセージ
                last_user_message = conversation_messages[-1]["content"]
                
                response = client.models.generate_content(
                    model="gemini-3.1-flash-lite",
                    config=types.GenerateContentConfig(
                        system_instruction=system_message
                    ),
                    contents=history
                    + [
                        types.Content(
                            role="user", parts=[types.Part(text=last_user_message)]
                        )
                    ],
                )
                safe_text = re.sub(r"@[\w\-\.]+(?:@[\w\-\.]+)?", "", response.text).strip()
                
                reply_note(safe_text)
            except Exception as e:
                reply_note("予期せぬエラーが発生した。何やってるんですか、エラーが出ないのは常識ですよね？？？")
                print(e)
        elif is_m:
            mk.notes_reactions_create(
                note_id=note["id"], reaction="⏱️"
            )
            try:
                # 非同期スレッドで速度測定を実行
                results = await asyncio.to_thread(run_speedtest_sync)
                
                download_speed = results.get("download", 0) / 1_000_000
                upload_speed = results.get("upload", 0) / 1_000_000
                ping = results.get("ping", 0)
                isp = results.get("client", {}).get("isp", "不明")
                server_name = results.get("server", {}).get("name", "不明")
                server_sponsor = results.get("server", {}).get("sponsor", "不明")
                
                current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")
                system_message = build_system_message(note["user"], current_time, "回線速度の測定を要求", econ_data, user_state)
                
                prompt = f"""
                回線速度の測定結果は以下の通りです：
                - ダウンロード速度: {download_speed:.2f} Mbps
                - アップロード速度: {upload_speed:.2f} Mbps
                - レイテンシ (Ping): {ping:.1f} ms
                - 接続プロバイダ: {isp}
                - 測定サーバー: {server_sponsor} ({server_name})

                この測定結果に基づき、あなたのキャラクター（傲慢で煽り気味なSBC御局娘であるOrangePi 4 Pro）として、結果を報告しつつ感想やアドバイス（回線が速い時の自慢や、遅い時の煽りなど）を含めて300文字以内で返答してください。
                """
                
                response = client.models.generate_content(
                    model="gemini-3.1-flash-lite",
                    config=types.GenerateContentConfig(
                        system_instruction=system_message
                    ),
                    contents=types.Content(
                        role="user", parts=[types.Part(text=prompt)]
                    ),
                )
                safe_text = re.sub(r"@[\w\-\.]+(?:@[\w\-\.]+)?", "", response.text).strip()
                
                reply_note(safe_text)
            except Exception as e:
                print(f"速度測定エラー: {e}")
                # エラー時もキャラクター性のあるエラー返答をする
                error_msg = "回線速度を測ろうとしたけれど、測定中にエラーが発生したわ。何やってるんですか、回線管理もろくにできないんですか？？？"
                reply_note(error_msg)


async def on_follow(user):
    try:
        mk.following_create(user["id"])
    except:
        pass


async def main():
    await asyncio.gather(runner(), teiki())


if __name__ == "__main__":
    asyncio.run(main())
