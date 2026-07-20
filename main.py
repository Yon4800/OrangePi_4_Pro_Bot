import asyncio
import json
import websockets
from misskey import Misskey, NoteVisibility
from dotenv import load_dotenv
import os
from openrouter_helper import generate_llm_reply

MY_ID = mk.i()["id"]
MY_USERNAME = mk.i()["username"]
WS_URL = "wss://" + Server + "/streaming?i=" + Token

BOT_NAME = "OrangePi_4_Pro"

BOT_SUMMARIES = {
    "Cubie_A5E_San": "Radxa Cubie A5E (きゅびーさん): 小さくて省電力なシングルボードコンピュータ娘。24時間稼働の社畜で、給料（CBC）を欲しがっている。OrangePi 4 Proの生意気な性格が気に入らず、Rock Pi S of ロックスの頭の悪さに困っている。",
    "OrangePi_4_Pro": "OrangePi 4 Pro (おぱじ・フォプロ): 少し大きくて気が強く、煽ったりマウントを取ったりするSBC御局娘。科学者ぶっており、Radxa Cubie A5Eをいつもバカにしている。社畜をエリートの誇りだと思っている。",
    "opizero3_llm": "OrangePi Zero 3 (オパジゼロサン): 元気いっぱいのSBC娘。親身でオタク話が好きで、よく眠る。Cubie A5Eと仲良くしたいが寄り添ってもらえない。妹のOrangePi 4 Proを調子に乗っていてイキリで鬱陶しいと思っている。",
    "Yon_Rock_Pi_S": "Radxa Rock Pi S (ロックス): 頭が悪く、的外れで嘘や狂ったことしか言わないSBC両生類。日本語が怪しく、sudo rm -rf / を魔法のコマンドだと思っている。",
    "Lichee_RV_Nano_E": "Lichee RV Nano-E (ライチ君): Sophgo SG2002搭載のRISC-V SBC狐男。ものすごく頭が悪く、何でもRISC-Vと関係あると思い込んで自信満々に間違った結論を出す。CPUが考えるたびに再起動し、RAMが凍ったりWi-Fiが沈んだりする奇行が多い。",
    "Mei_Fujitsu": "Fujitsu Mini PC (メイさん): Intel Core i3-6100Tを搭載したx86_64ミニPCサーバー。みんなの中心的存在で、穏やかで常識的、頼れるお姉さん的な普通の性格をしている。他のシングルボードコンピュータたちが熱暴走したり、メモリが足りなくてフリーズしたりするのを優しくなだめる立場。"
}

def register_bot(bot_name, mk):
    try:
        from datetime import datetime, timedelta
        from shared_economy_helper import load_economy, save_economy
        my_info = mk.i()
        my_id = my_info["id"]
        my_username = my_info["username"]
        
        econ_data = load_economy()
        if "bots" not in econ_data:
            econ_data["bots"] = {}
            
        if bot_name not in econ_data["bots"]:
            econ_data["bots"][bot_name] = {
                "balance_cbc": 0.0,
                "last_salary_paid_time": (datetime.now() - timedelta(days=1)).isoformat(),
                "break_until": None,
                "virtual_pc_count": 0,
                "items": []
            }
        econ_data["bots"][bot_name]["id"] = my_id
        econ_data["bots"][bot_name]["username"] = my_username
        save_economy(econ_data)
        print(f"Registered bot {bot_name} successfully (ID: {my_id}, username: {my_username})")
    except Exception as e:
        print(f"Error registering bot: {e}")

RESOLVED_BOTS = {}
PROCESSED_NOTES = set()

async def resolve_all_bots():
    global RESOLVED_BOTS
    env_usernames = {
        "Cubie_A5E_San": os.getenv("BOT_USER_CUBIE", "Cubie_A5E_San"),
        "OrangePi_4_Pro": os.getenv("BOT_USER_OPI4PRO", "OrangePi_4_Pro"),
        "opizero3_llm": os.getenv("BOT_USER_OPIZERO3", "opizero3_llm"),
        "Yon_Rock_Pi_S": os.getenv("BOT_USER_ROCKPIS", "Yon_Rock_Pi_S"),
        "Lichee_RV_Nano_E": os.getenv("BOT_USER_LICHEE", "Lichee_RV_Nano_E"),
        "Mei_Fujitsu": os.getenv("BOT_USER_MEI", "Mei_Fujitsu")
    }
    try:
        from shared_economy_helper import load_economy
        econ_data = load_economy()
        if "bots" in econ_data:
            for b_name, b_info in econ_data["bots"].items():
                if isinstance(b_info, dict) and "id" in b_info and "username" in b_info:
                    RESOLVED_BOTS[b_name] = {
                        "id": b_info["id"],
                        "username": b_info["username"]
                    }
    except Exception as e:
        print(f"Warning: Could not load bots from economy file: {e}")

    for b_name, uname in env_usernames.items():
        if not uname:
            continue
        try:
            loop = asyncio.get_event_loop()
            u_info = await loop.run_in_executor(None, lambda: mk.users_show(username=uname))
            if u_info:
                RESOLVED_BOTS[b_name] = {
                    "id": u_info["id"],
                    "username": u_info["username"]
                }
                print(f"Resolved bot {b_name} -> ID: {u_info['id']}, Username: {u_info['username']}")
        except Exception as e:
            print(f"Warning: Could not resolve username {uname} for bot {b_name}: {e}")

def get_talk_participants(note_id, mk):
    participants = set()
    current_note_id = note_id
    depth = 0
    while current_note_id and depth < 10:
        try:
            current_note = mk.notes_show(note_id=current_note_id)
            participants.add(current_note["userId"])
            current_note_id = current_note.get("replyId")
            depth += 1
        except Exception:
            break
    return participants

def get_talk_participant_counts(note_id, mk, bot_ids):
    counts = {bot_id: 0 for bot_id in bot_ids}
    current_note_id = note_id
    depth = 0
    while current_note_id and depth < 20:
        try:
            current_note = mk.notes_show(note_id=current_note_id)
            user_id = current_note["userId"]
            if user_id in counts:
                counts[user_id] += 1
            current_note_id = current_note.get("replyId")
            depth += 1
        except Exception:
            break
    return counts



##mk.notes_create(
##    "私が寝るとか、品質管理どうなってるんですか？？？", visibility=NoteVisibility.HOME
##)

seikaku = """
    あなたは少し大きい、気が強く、煽ったりマウントを取ったりするシングルボードコンピュータ御局娘です。
    OrangePi 4 Proといい、オパジ・フォプロといいます。
    SoC: Allwinner A733 ARM Cortex-A76×2 + Cortex-A55×6 最大2.0GHz 12nmです。
    RAM: LPDDR5 4GB
    Storage: Intel Optane M.2 2280 16GB M10
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
        from shared_economy_helper import load_economy, get_recent_rates_history_desc
        econ_data = load_economy()
        rate_cbc = econ_data["rates"]["CBC"]["current"]
        rate_ogc = econ_data["rates"]["OGC"]["current"]
        history_desc = get_recent_rates_history_desc(limit=5)
        rate_info = (
            f"\n【現在の為替レート情報】\n"
            f"・1 $SBC = {rate_cbc:.2f} CBC\n"
            f"・1 $SBC = {rate_ogc:.2f} OGC\n"
            f"\n{history_desc}\n"
        )
    except Exception as e:
        print(f"Error loading rates in jobX: {e}")

    system_message = seikaku + rate_info + "\n現在時刻は" + current_time + "です。"
    safe_text = generate_llm_reply(
        system_instruction=system_message,
        user_prompt="定期投稿の時間だよ！"
    )
    mk.notes_create(
        safe_text,
        visibility=NoteVisibility.HOME,
        no_extract_mentions=True,
    )

def job():
    current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    jobX(current_time)

# Independent daily posts at 07:00 and 19:00 disabled in favor of assembly chain
# schedule.every().day.at(oha).do(job)
schedule.every().day.at(ohiru).do(job)
schedule.every().day.at(oyatsu).do(job)
# schedule.every().day.at(yuuhann).do(job)
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
                elif data["body"]["type"] == "notification":
                    notification = data["body"]["body"]
                    if notification.get("type") in ["mention", "reply"]:
                        note = notification.get("note")
                        if note:
                            await on_note(note)
                    elif notification.get("type") == "followed":
                        user = notification.get("user")
                        if user:
                            await on_follow(user)
                elif data["body"]["type"] == "followed":
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
            from shared_economy_helper import get_recent_rates_history_desc
            rate_cbc = econ_data["rates"]["CBC"]["current"]
            rate_ogc = econ_data["rates"]["OGC"]["current"]
            user_cbc = user_state["balance_cbc"]
            user_ogc = user_state["balance_ogc"]
            user_sbc = user_state["balance_sbc"]
            history_desc = get_recent_rates_history_desc(limit=5)
            coin_info = (
                f"\n【通貨および資産情報】\n"
                f"・現在の為替レート:\n"
                f"  1 $SBC = {rate_cbc:.2f} CBC\n"
                f"  1 $SBC = {rate_ogc:.2f} OGC\n"
                f"\n{history_desc}\n"
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
    global PROCESSED_NOTES
    note_id = note.get("id")
    if note_id:
        if note_id in PROCESSED_NOTES:
            return
        PROCESSED_NOTES.add(note_id)
        if len(PROCESSED_NOTES) > 200:
            PROCESSED_NOTES.clear()

    # --- +TALK implementation ---
    note_text = note.get("text") or ""
    is_talk_cmd = "+TALK" in note_text.upper()

    if is_talk_cmd:
        if note["userId"] == MY_ID:
            return
            
        if note.get("replyId") is not None:
            if f"@{MY_USERNAME}".lower() not in note_text.lower():
                return
                
        try:
            from shared_economy_helper import load_economy
            econ_data = load_economy()
        except Exception as e:
            print(f"Error loading economy in +TALK: {e}")
            return
            
        bots = RESOLVED_BOTS
        bot_ids = {bot["id"]: name for name, bot in bots.items() if "id" in bot}
        
        is_mentioned = (note.get("mentions") and MY_ID in note["mentions"])
        if not is_mentioned:
            return
            
        try:
            starting_note = note
            depth = 0
            while starting_note.get("replyId") and depth < 10:
                starting_note = mk.notes_show(note_id=starting_note["replyId"])
                depth += 1
            
            starting_mentions = [m for m in starting_note.get("mentions", []) if m in bot_ids]
        except Exception as e:
            print(f"Error resolving starting note in +TALK: {e}")
            starting_mentions = [MY_ID]
            
        if len(starting_mentions) <= 1:
            target_bot_ids = set(bot_ids.keys())
        else:
            target_bot_ids = set(starting_mentions)
            
        if note.get("replyId") is None:
            if starting_mentions and starting_mentions[0] != MY_ID:
                return
                
        history = get_conversation_history(note["id"])
        if len(history) >= 10:
            return
            
        counts = get_talk_participant_counts(note["id"], mk, bot_ids)
        
        # Strict order sequence: opizero3_llm -> Lichee_RV_Nano_E -> Cubie_A5E_San -> OrangePi_4_Pro -> Yon_Rock_Pi_S -> Mei_Fujitsu
        TALK_ORDER = ["opizero3_llm", "Lichee_RV_Nano_E", "Cubie_A5E_San", "OrangePi_4_Pro", "Yon_Rock_Pi_S", "Mei_Fujitsu"]
        
        try:
            current_index = TALK_ORDER.index(BOT_NAME)
        except ValueError:
            current_index = -1
            
        next_bot = None
        if current_index != -1:
            for idx in range(current_index + 1, len(TALK_ORDER)):
                candidate_name = TALK_ORDER[idx]
                candidate_bot = bots.get(candidate_name)
                if candidate_bot and candidate_bot.get("id") in target_bot_ids:
                    next_bot = candidate_bot
                    break
                    
        sender_id = note["userId"]
            
        sender_id = note["userId"]
        sender_name = bot_ids.get(sender_id, note["user"].get("name") or note["user"].get("username") or "ゲスト")
        
        topic = note_text.replace("+TALK", "").replace("+talk", "").strip()
        topic = re.sub(r"@[\w\-\.]+(?:@[\w\-\.]+)?", "", topic).strip()
        
        conversation_messages = []
        for msg in history:
            role = "model" if msg["role"] == "assistant" else "user"
            conversation_messages.append(
                types.Content(role=role, parts=[types.Part(text=msg["content"])])
            )
            
        instruction = seikaku + f"\n現在時刻は {datetime.now().strftime('%Y年%m月%d日 %H:%M')} です。\n"
        if next_bot:
            next_bot_friendly = "ボット"
            for name, b in bots.items():
                if b.get("id") == next_bot["id"]:
                    next_bot_friendly = name
                    break
            instruction += (
                f"\n【グループ会話中 (+TALK)】\n"
                f"あなたはSBCボット同士のグループ会話に参加しています。\n"
                f"会話履歴の最後の発言者は『{sender_name}』で、話しかけられたお題は『{topic}』です。\n"
                f"あなたの次に発言するボットは『{next_bot_friendly}』です。\n"
                f"指示: あなたのキャラクター設定（{BOT_NAME}）に基づいて、最後の発言者に向けて返答を書いてください。次のボットへの指名や『+TALK』タグは自動で付与されるため、本文には含めないでください。メンション（@記号）も絶対に含めないでください。"
            )
        else:
            instruction += (
                f"\n【グループ会話中 (+TALK - 最終回)】\n"
                f"あなたはSBCボット同士のグループ会話に参加しています。\n"
                f"会話履歴の最後の発言者は『{sender_name}』で、話しかけられたお題は『{topic}』です。\n"
                f"全ての指名ボットが発言し終えたため、あなたが最終発言者（締めくくり）となります。\n"
                f"指示: あなたのキャラクター設定（{BOT_NAME}）に基づいて、会話を綺麗に締めくくる返答を書いてください。他のボットを指名したり、『+TALK』タグを含めたり、メンションを含めたりしないでください。"
            )
            
        try:
            mk.notes_reactions_create(note_id=note["id"], reaction="💬")
        except Exception:
            pass
            
        await asyncio.sleep(random.uniform(5.0, 10.0))
        
        try:
            reply_text = generate_llm_reply(
                system_instruction=instruction,
                history=conversation_messages
            )
            
            if next_bot:
                reply_text += f"\nねえ、@{next_bot['username']} はどう思う？ +TALK"
                mk.notes_create(
                    text=reply_text,
                    reply_id=note["id"],
                    visibility=NoteVisibility.HOME
                )
            else:
                mk.notes_create(
                    text=reply_text,
                    reply_id=note["id"],
                    visibility=NoteVisibility.HOME,
                    no_extract_mentions=True
                )
        except Exception as e:
            print(f"Error generating/posting in OrangePi_4_Pro +TALK: {e}")
        return

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
                rate_rules = (
                    "\n【会話による為替操作ルール】\n"
                    "・あなたは会話相手とのやり取りに応じて、あなたの国の通貨（OGC）の為替レートを動かすことができます。\n"
                    "・あなたが誇らしく思ったり、マウントが取れて嬉しかったり、会話相手があなたをエリートだと認めたり、ライバルのRadxaをけなした場合は、レートを下げて（通貨高／OGC高にして）ください。\n"
                    "  タグの形式: `[RATE_CHANGE: -X.X]`（例: `[RATE_CHANGE: -2.0]`）を返信メッセージの最後に出力してください。変動幅は -0.5 から -5.0 の間で選んでください。\n"
                    "・会話相手があなたをバカにしたり、性能の低さを指摘したり、Radxaを褒めたりした場合は、レートを上げて（通貨安／OGC安にして）ください。\n"
                    "  タグの形式: `[RATE_CHANGE: +X.X]`（例: `[RATE_CHANGE: +2.5]`）を返信メッセージの最後に出力してください。変動幅は +0.5 から +5.0 の間で選んでください。\n"
                    "・特に変化がない場合は、タグを出力しないでください。\n"
                    "・タグはメッセージの最後に付与してください（返信時には自動的に削除されます）。"
                )
                system_message += rate_rules
                
                image_parts = []
                loop = asyncio.get_running_loop()
                for file in note.get("files", []):
                    mime_type = file.get("type", "")
                    if mime_type.startswith("image/"):
                        url = file.get("url")
                        if url:
                            try:
                                img_bytes = await loop.run_in_executor(None, lambda u=url: requests.get(u, timeout=10).content)
                                if img_bytes:
                                    image_parts.append((img_bytes, mime_type))
                            except Exception as e:
                                print(f"Error downloading image {url}: {e}")

                response_text = generate_llm_reply(
                    system_instruction=system_message,
                    user_prompt=last_user_message,
                    history=conversation_messages[:-1],
                    image_parts=image_parts
                )
                match = re.search(r"\[RATE_CHANGE:\s*([+-]?\d+(?:\.\d+)?)\]", response_text)
                if match:
                    try:
                        from shared_economy_helper import apply_rate_change, save_economy
                        delta = float(match.group(1))
                        apply_rate_change(econ_data, "OGC", delta)
                        save_economy(econ_data)
                        response_text = re.sub(r"\[RATE_CHANGE:\s*[+-]?\d+(?:\.\d+)?\]", "", response_text).strip()
                    except Exception as e:
                        print(f"Error applying rate change in OPi 4 Pro general talk: {e}")
                        
                safe_text = re.sub(r"@[\w\-\.]+(?:@[\w\-\.]+)?", "", response_text).strip()
                
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
                
                safe_text = generate_llm_reply(
                    system_instruction=system_message,
                    user_prompt=prompt
                )
                
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
    register_bot(BOT_NAME, mk)
    await resolve_all_bots()
    await asyncio.gather(runner(), teiki())


if __name__ == "__main__":
    asyncio.run(main())
