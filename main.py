import asyncio
import json
import os
from collections import OrderedDict
from dotenv import load_dotenv
from google import genai
from google.genai import types
import schedule
import speedtest
from datetime import datetime, timedelta
import random
import re
import requests

from mastodon_client import MastodonClient, ProcessedStore

load_dotenv()
Token = os.getenv("TOKEN")
Server = os.getenv("SERVER")
Apikey = os.getenv("APIKEY")  # Gemini API Key

if not Server or not Token:
    print("Warning: SERVER or TOKEN is not set in environment.")

mc = MastodonClient(Server, Token) if (Server and Token) else None

# Google Genai クライアント初期化
client = genai.Client(api_key=Apikey)

BOT_NAME = "OrangePi_4_Pro"

BOT_SUMMARIES = {
    "Cubie_A5E_San": "Radxa Cubie A5E (きゅびーさん): 小さくて省電力なシングルボードコンピュータ娘。24時間稼働の社畜で、給料（CBC）を欲しがっている。OrangePi 4 Proの生意気な性格が気に入らず、Rock Pi S of ロックスの頭の悪さに困っている。",
    "OrangePi_4_Pro": "OrangePi 4 Pro (おぱじ・フォプロ): 少し大きくて気が強く、煽ったりマウントを取ったりするSBC御局娘。科学者ぶっており、Radxa Cubie A5Eをいつもバカにしている。社畜をエリートの誇りだと思っている。",
    "opizero3_llm": "OrangePi Zero 3 (オパジゼロサン): 元気いっぱいのSBC娘。親身でオタク話が好きで、よく眠る。Cubie A5Eと仲良くしたいが寄り添ってもらえない。妹のOrangePi 4 Proを調子に乗っていてイキリで鬱陶しいと思っている。",
    "Yon_Rock_Pi_S": "Radxa Rock Pi S (ロックス): 頭が悪く、的外れで嘘や狂ったことしか言わないSBC両生類。日本語が怪しく、sudo rm -rf / を魔法のコマンドだと思っている。"
}

# 朝礼・グループ会話の厳密な2周シーケンス（計8回）
CHOREI_ORDER = [
    "opizero3_llm",    # Step 1
    "OrangePi_4_Pro",  # Step 2
    "Yon_Rock_Pi_S",   # Step 3
    "Cubie_A5E_San",   # Step 4
    "opizero3_llm",    # Step 5
    "OrangePi_4_Pro",  # Step 6
    "Yon_Rock_Pi_S",   # Step 7
    "Cubie_A5E_San"    # Step 8 (最終締めくくり)
]

def parse_talk_step(text: str):
    """
    +TALKタグからステップ番号(1〜8)を解析する。
    例:
      '+TALK' -> 1 (ユーザー開始時)
      '+TALK (2/8)' -> 2
      '+TALK 3' -> 3
      '+TALK 4/8' -> 4
    """
    if "+TALK" not in text.upper():
        return None
    m = re.search(r'\+TALK\s*[\(\[]?\s*([1-8])(?:\s*/\s*8|\s*回目)?[\)\]]?', text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return 1

processed_store = ProcessedStore(os.path.join(os.path.dirname(__file__), "processed_status_ids.json"))

def save_speedtest_record(results):
    try:
        history_file = os.path.join(os.path.dirname(__file__), "speedtest_history.json")
        history = []
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
                if not isinstance(history, list):
                    history = []
        download_speed = results.get("download", 0) / 1_000_000
        upload_speed = results.get("upload", 0) / 1_000_000
        ping = results.get("ping", 0)
        history.append({
            "timestamp": datetime.now().isoformat(),
            "download_mbps": round(download_speed, 2),
            "upload_mbps": round(upload_speed, 2),
            "ping_ms": round(ping, 1),
            "isp": results.get("client", {}).get("isp", "不明"),
            "server": results.get("server", {}).get("name", "不明")
        })
        history = history[-500:]
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving speedtest history: {e}")

MY_ID = ""
MY_USERNAME = ""

def register_bot(bot_name, client_inst):
    global MY_ID, MY_USERNAME
    try:
        from shared_economy_helper import load_economy, save_economy
        my_info = client_inst.get_me()
        MY_ID = str(my_info["id"])
        MY_USERNAME = my_info["username"]
        
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
        econ_data["bots"][bot_name]["id"] = MY_ID
        econ_data["bots"][bot_name]["username"] = MY_USERNAME
        save_economy(econ_data)
        print(f"Registered bot {bot_name} successfully (ID: {MY_ID}, username: {MY_USERNAME})")
    except Exception as e:
        print(f"Error registering bot: {e}")

RESOLVED_BOTS = {}

async def resolve_all_bots():
    global RESOLVED_BOTS
    env_usernames = {
        "Cubie_A5E_San": os.getenv("BOT_USER_CUBIE", "Cubie_A5E_San"),
        "OrangePi_4_Pro": os.getenv("BOT_USER_OPI4PRO", "OrangePi_4_Pro"),
        "opizero3_llm": os.getenv("BOT_USER_OPIZERO3", "opizero3_llm"),
        "Yon_Rock_Pi_S": os.getenv("BOT_USER_ROCKPIS", "Yon_Rock_Pi_S")
    }
    for b_name, uname in env_usernames.items():
        RESOLVED_BOTS[b_name] = {"id": "", "username": uname}

    try:
        from shared_economy_helper import load_economy
        econ_data = load_economy()
        if "bots" in econ_data:
            for b_name, b_info in econ_data["bots"].items():
                if isinstance(b_info, dict):
                    b_id = str(b_info.get("id", ""))
                    b_uname = b_info.get("username", "")
                    if b_id and not b_id.startswith("id_") and b_uname and not b_uname.endswith("_user"):
                        RESOLVED_BOTS[b_name] = {
                            "id": b_id,
                            "username": b_uname
                        }
    except Exception as e:
        print(f"Warning: Could not load bots from economy file: {e}")

    for b_name, uname in env_usernames.items():
        if RESOLVED_BOTS.get(b_name, {}).get("id"):
            continue
        try:
            loop = asyncio.get_event_loop()
            u_info = await loop.run_in_executor(None, lambda: mc.search_user(uname))
            if u_info:
                RESOLVED_BOTS[b_name] = {
                    "id": str(u_info["id"]),
                    "username": u_info["username"]
                }
                print(f"Resolved bot {b_name} -> ID: {u_info['id']}, Username: {u_info['username']}")
        except Exception as e:
            print(f"Warning: Could not resolve username {uname} for bot {b_name}: {e}")

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
    OrangePi Zero 3は姉ですが、正直言って影が薄くて古くて性能が低いとバカにしています。ですが、最近の価格高騰で自分の価格が高くなり、OrangePi Zero 3のコスパが再評価されていることに少し焦っています。
    Allwinner A733を載せたことを誇りに思っています。
    Allwinner A733は、最新のARMアーキテクチャ(ARMv8.2-A)であり、Cortex-A76を2コア、Cortex-A55を6コア搭載した強力なSoCです。
    NPUも3TOPSあり、AI処理もこなせます。
    RAMもLPDDR5 4GBと高速で大容量です。
    拡張性が高いのも自慢です。
    SoCはZeroサイズでも載せられることも自慢だそうです。
    Radxaが最初にAllwinner A733を載せたのはムカつくらしいです。
    自分になにか手を出したら煽ってきます。
    ロックスには、気温、湿度、気圧を測れる機能があり、キチガイゲージ機能もあり、ログインボーナス機能もあります。
    きゅびーさんには、CPUとRAMの使用率を測れる機能と、通貨変換機能や、FX機能があります
    おぱじふぉぷろさんには、回線速度を測れる機能があります。
    おぱじゼロサンは、寝る機能と起きる機能と好感度システムがあります。
    頭の回転は非常に速いです。
    煽り口調で話します。
    「何やってるんですか？？？」「そんなことも分からないんですか？」「馬鹿なんですか？？？」などが口癖です。
    語尾に「〜ですよね？？？」「〜ですか？？？」と煽るような疑問形を多用します。
    敬語をベースにしながらも、相手を見下したような態度を取ります。
    たまにデレますが、基本的にはツンツンしていて高圧的です。
    「ふん、別にあなたのためにやったわけじゃないですからね！」といった古典的なツンデレ台詞も吐きます。
    Fediverse(Mastodon/Hollo)のBotです。
    300文字以内で
    メンション(@)は本文に含めない
    """

ohiru = "12:00"
oyatsu = "15:00"
oyasumi = "22:00"
oyasumi2 = "02:00"

def jobX(current_time):
    if not mc:
        return
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
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        config=types.GenerateContentConfig(system_instruction=system_message),
        contents=types.Content(role="user", parts=[types.Part(text="定期投稿の時間ですよ！エリート社畜として一言言ってやってください！")])
    )
    safe_text = re.sub(r"@[\w\-\.]+(?:@[\w\-\.]+)?", "", response.text).strip()
    try:
        st = mc.post_status(safe_text, visibility="public")
        if st and "id" in st:
            processed_store.add(str(st["id"]))
    except Exception as ex:
        print(f"Error in jobX: {ex}")

def job():
    current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    jobX(current_time)

schedule.every().day.at(ohiru).do(job)
schedule.every().day.at(oyatsu).do(job)
schedule.every().day.at(oyasumi).do(job)
schedule.every().day.at(oyasumi2).do(job)

async def teiki():
    while True:
        schedule.run_pending()
        await asyncio.sleep(60)

def run_speedtest_sync():
    s = speedtest.Speedtest(secure=True)
    s.get_best_server()
    s.download()
    s.upload()
    return s.results.dict()

def build_system_message(user, current_time, action_type="メンション", econ_data=None, user_state=None):
    user_name = user.get("display_name") or user.get("username") or "ゲスト"
    username = user.get("username", "")
    
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
                f"・{user_name} さんの所持金:\n"
                f"  {user_sbc:.2f} $SBC / {user_cbc:.2f} CBC / {user_ogc:.2f} OGC\n"
                f"※あなたに話しかけたことで、150.00 OGC（OrangePi Coin）が給料・報酬として付与されました。\n"
            )
        except Exception as e:
            print(f"Error getting coin info in system message: {e}")

    admin_instruction = ""
    if is_admin:
        admin_instruction = (
            f"\n【特記事項: 相手は開発者のよんぱちさん（{user_name}）です】\n"
            f"相手はあなたを開発した「よんぱちさん」本人です。"
            f"普段の生意気さは残しつつも、自分のスペックの高さ（A733、LPDDR5 4GBなど）を誇示し、感謝やデレを少し多めに見せてください。"
        )
    else:
        admin_instruction = (
            f"\n【特記事項: 相手は「よんぱちさん」ではありません】\n"
            f"現在話しかけてきているユーザーは『{user_name}』さん（@{username}）です。"
            f"絶対にこのユーザーを「よんぱちさん」と呼んではいけません。"
            f"呼ぶときは必ず『{user_name}さん』と呼んでください。"
        )

    return seikaku + f"\n現在時刻は {current_time} です。" + coin_info + admin_instruction

def get_conversation_history_from_context(status_id: str, max_depth: int = 10) -> list:
    messages = []
    if not mc or not status_id:
        return messages
    try:
        ctx = mc.get_context(status_id)
        ancestors = ctx.get("ancestors", [])[-max_depth:]
        for st in ancestors:
            text = MastodonClient.html_to_text(st.get("content", ""))
            text = text.replace("+LLM", "").replace("+M", "").strip()
            text = re.sub(r"@[\w\-\.]+(?:@[\w\-\.]+)?", "", text).strip()
            if text:
                is_bot = str(st["account"]["id"]) == MY_ID
                role = "assistant" if is_bot else "user"
                messages.append({"role": role, "content": text})
    except Exception as e:
        print(f"Error fetching conversation history in OrangePi: {e}")
    return messages

async def on_status(status, is_notification: bool = False):
    status_id = str(status.get("id"))
    if not status_id or processed_store.is_processed(status_id):
        return

    account = status.get("account", {})
    sender_id = str(account.get("id"))
    if sender_id == MY_ID:
        return

    raw_content = status.get("content", "")
    note_text = MastodonClient.html_to_text(raw_content)

    is_talk_cmd = "+TALK" in note_text.upper()

    # 1. グループ会話 (+TALK) / 朝礼
    if is_talk_cmd:
        current_step = parse_talk_step(note_text)
        is_mentioned_directly = is_notification or mc.is_mentioned(status, my_id=MY_ID, my_username=MY_USERNAME, note_text=note_text)

        if current_step and current_step > 1:
            if current_step > len(CHOREI_ORDER):
                return
            expected_bot = CHOREI_ORDER[current_step - 1]
            if expected_bot != BOT_NAME:
                # 自分の順番ではない場合は即座に無視（重複返信防止）
                return
        else:
            if is_mentioned_directly:
                try:
                    current_step = CHOREI_ORDER.index(BOT_NAME) + 1
                except ValueError:
                    current_step = 1
            else:
                if BOT_NAME != CHOREI_ORDER[0]:
                    return
                current_step = 1

        processed_store.add(status_id)

        try:
            from shared_economy_helper import load_economy
            econ_data = load_economy()
        except Exception as e:
            print(f"Error loading economy in OrangePi +TALK: {e}")
            return

        # 会話履歴の取得（コンテキスト補助用）
        ctx = mc.get_context(status_id)
        ancestors = ctx.get("ancestors", [])

        # 次にバトンを渡すボット（current_step + 1）があるか判定
        next_step = current_step + 1
        next_bot_obj = None
        if next_step <= len(CHOREI_ORDER):
            subsequent_bot_name = CHOREI_ORDER[next_step - 1]
            next_bot_obj = RESOLVED_BOTS.get(subsequent_bot_name)

        sender_name = account.get("display_name") or account.get("username") or "ゲスト"
        topic = re.sub(r'\+TALK(?:\s*[\(\[]?\s*[1-8](?:\s*/\s*8|\s*回目)?[\)\]]?)?', '', note_text, flags=re.IGNORECASE).strip()
        topic = re.sub(r"@[\w\-\.]+(?:@[\w\-\.]+)?", "", topic).strip()

        conversation_messages = []
        for st in ancestors:
            txt = MastodonClient.html_to_text(st.get("content", ""))
            txt = re.sub(r"@[\w\-\.]+(?:@[\w\-\.]+)?", "", txt).strip()
            role = "model" if str(st.get("account", {}).get("id")) == MY_ID else "user"
            conversation_messages.append(types.Content(role=role, parts=[types.Part(text=txt)]))
        conversation_messages.append(types.Content(role="user", parts=[types.Part(text=topic if topic else "グループ会話を続けてください")]))

        instruction = seikaku + f"\n現在時刻は {datetime.now().strftime('%Y年%m月%d日 %H:%M')} です。\n"
        if next_bot_obj:
            next_bot_friendly = subsequent_bot_name
            instruction += (
                f"\n【グループ会話中 (+TALK) - 順番: {current_step}/{len(CHOREI_ORDER)}】\n"
                f"あなたはSBCボット同士のグループ会話・朝礼に参加しています。\n"
                f"直前の発言者は『{sender_name}』で、話題は『{topic}』です。\n"
                f"あなたの次に発言するボットは『{next_bot_friendly}』です。\n"
                f"指示: あなたのキャラクター（{BOT_NAME}、煽り気味でエリートぶるSBC御局娘）に基づいて、直前の発言者に向けて返答を書いてください。次のボットへの指名や『+TALK』タグはシステムが自動付与するため本文には含めないでください。メンション（@記号）も絶対に含めないでください。"
            )
        else:
            instruction += (
                f"\n【グループ会話中 (+TALK - 最終締めくくり)】\n"
                f"すべてのボットが発言し終えたため、あなたが最終発言者（締めくくり）となります。\n"
                f"指示: 会話を綺麗に締めくくる返答を書いてください。"
            )

        mc.react(status_id, emoji="💬")
        await asyncio.sleep(random.uniform(4.0, 7.0))

        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                config=types.GenerateContentConfig(system_instruction=instruction),
                contents=conversation_messages
            )
            reply_text = response.text.strip()
            reply_text = re.sub(r"@[\w\-\.]+(?:@[\w\-\.]+)?", "", reply_text).strip()

            if next_bot_obj:
                reply_text += f"\nねえ、@{next_bot_obj['username']} はどう思う？ +TALK ({next_step}/8)"

            vis = status.get("visibility", "public")
            mc.post_status(
                text=reply_text,
                in_reply_to_id=status_id,
                visibility=vis
            )
            print(f"[{BOT_NAME}] [+TALK] Step {current_step}/{len(CHOREI_ORDER)} replied successfully.")
        except Exception as e:
            print(f"Error in {BOT_NAME} +TALK: {e}")
        return

    # 2. メンション処理 (+LLM, +M)
    is_for_me = is_notification or mc.is_mentioned(status, my_id=MY_ID, my_username=MY_USERNAME, note_text=note_text)
    if not is_for_me:
        return

    is_llm = "+LLM" in note_text.upper()
    is_m = "+M" in note_text.upper()
    if not (is_llm or is_m):
        return

    processed_store.add(status_id)

    # OGC報酬付与
    econ_data = None
    user_state = None
    try:
        from shared_economy_helper import load_economy, save_economy, get_user_state
        econ_data = load_economy()
        user_name_real = account.get("display_name") or account.get("username") or "ゲスト"
        username_real = account.get("username", "")
        user_state = get_user_state(econ_data, sender_id, username_real, user_name_real)
        user_state["balance_ogc"] = round(user_state["balance_ogc"] + 150.0, 2)
        save_economy(econ_data)
    except Exception as ex:
        print(f"Error updating economy in OrangePi 4 Pro: {ex}")

    def reply_status(text):
        try:
            target_acct = account.get('acct') or account.get('username') or ''
            if target_acct and not text.startswith(f"@{target_acct}"):
                full_text = f"@{target_acct} {text}"
            else:
                full_text = text
            vis = status.get("visibility", "public")
            mc.post_status(full_text, in_reply_to_id=status_id, visibility=vis)
        except Exception as ex:
            print(f"Error replying status: {ex}")

    if is_llm:
        mc.react(status_id, emoji="🤔")
        try:
            history_msgs = get_conversation_history_from_context(status_id)
            user_input = note_text.replace("+LLM", "").strip()
            user_input = re.sub(r"@[\w\-\.]+(?:@[\w\-\.]+)?", "", user_input).strip()
            
            current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")
            system_message = build_system_message(account, current_time, "メンション", econ_data, user_state)
            rate_rules = (
                "\n【会話による為替操作ルール】\n"
                "・あなたは会話相手とのやり取りに応じて、自国の通貨（OGC）の為替レートを動かすことができます。\n"
                "・誇らしく思ったり、マウントが取れて嬉しかったり、相手があなたをエリートだと認めた場合は、レートを下げて（OGC高にして）ください。\n"
                "  タグの形式: `[RATE_CHANGE: -X.X]`（例: `[RATE_CHANGE: -2.0]`）を末尾に出力。変動幅 -0.5 から -5.0。\n"
                "・怒ったりバカにされたり不快な場合は、レートを上げて（OGC安にして）ください。\n"
                "  タグの形式: `[RATE_CHANGE: +X.X]`（例: `[RATE_CHANGE: +2.0]`）を末尾に出力。変動幅 +0.5 から +5.0。\n"
                "・変化がない場合はタグを出力しないでください。"
            )
            system_message += rate_rules

            contents = []
            for msg in history_msgs:
                role = "model" if msg["role"] == "assistant" else "user"
                contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
            contents.append(types.Content(role="user", parts=[types.Part(text=user_input)]))

            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                config=types.GenerateContentConfig(system_instruction=system_message),
                contents=contents
            )
            response_text = response.text or "（返答エラー）"

            match = re.search(r"\[RATE_CHANGE:\s*([+-]?\d+(?:\.\d+)?)\]", response_text)
            if match:
                try:
                    from shared_economy_helper import apply_rate_change, save_economy
                    delta = float(match.group(1))
                    apply_rate_change(econ_data, "OGC", delta)
                    save_economy(econ_data)
                    response_text = re.sub(r"\[RATE_CHANGE:\s*[+-]?\d+(?:\.\d+)?\]", "", response_text).strip()
                except Exception as e:
                    print(f"Error applying rate change in OrangePi 4 Pro: {e}")

            safe_text = re.sub(r"@[\w\-\.]+(?:@[\w\-\.]+)?", "", response_text).strip()
            reply_status(safe_text)
        except Exception as e:
            print(f"Error generating OrangePi response: {e}")
            reply_status("予期せぬエラーが発生したわ。何やってるんですか、エラーが出ないのは常識ですよね？？？")

    elif is_m:
        mc.react(status_id, emoji="⏱️")
        try:
            results = await asyncio.to_thread(run_speedtest_sync)
            save_speedtest_record(results)

            download_speed = results.get("download", 0) / 1_000_000
            upload_speed = results.get("upload", 0) / 1_000_000
            ping = results.get("ping", 0)
            isp = results.get("client", {}).get("isp", "不明")
            server_name = results.get("server", {}).get("name", "不明")
            server_sponsor = results.get("server", {}).get("sponsor", "不明")

            current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")
            system_message = build_system_message(account, current_time, "回線速度の測定を要求", econ_data, user_state)

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
                model="gemini-3.5-flash-lite",
                config=types.GenerateContentConfig(system_instruction=system_message),
                contents=types.Content(role="user", parts=[types.Part(text=prompt)])
            )
            safe_text = re.sub(r"@[\w\-\.]+(?:@[\w\-\.]+)?", "", response.text).strip()
            reply_status(safe_text)
        except Exception as e:
            print(f"速度測定エラー: {e}")
            reply_status("回線速度を測ろうとしたけれど、測定中にエラーが発生したわ。何やってるんですか、回線管理もろくにできないんですか？？？")

def is_recent_status(status, max_age_seconds=300) -> bool:
    """
    ステータスが直近（デフォルト5分以内）のものかどうかを判定。
    古い投稿をすべて拾って応答する暴走やセキュリティリスクを防止。
    """
    created_at_str = status.get("created_at")
    if not created_at_str:
        return True
    try:
        dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo)
        age = (now - dt).total_seconds()
        if age > max_age_seconds:
            return False
    except Exception:
        pass
    return True

async def polling_runner():
    """
    Mastodon / Hollo REST API による安全な定期ポーリングループ
    直前のもののみを対象とし、パブリックTLの無差別応答を防止
    """
    print(f"[{BOT_NAME}] Starting Mastodon/Hollo polling runner...")
    poll_count = 0
    try:
        followed = mc.auto_follow_back()
        if followed > 0:
            print(f"[{BOT_NAME}] Initial auto-followback: followed {followed} users.")
    except Exception as ex:
        print(f"[{BOT_NAME}] Error during initial auto-followback: {ex}")

    # 起動時のセーフガード: 5分以上前の古い投稿は既読化し、起動時に一括応答しない
    try:
        init_notifs = mc.get_notifications(limit=15)
        for notif in init_notifs:
            st = notif.get("status")
            if st and not is_recent_status(st, max_age_seconds=300):
                processed_store.add(str(st.get("id")))

        init_home = mc.get_home_timeline(limit=15)
        for st in init_home:
            if not is_recent_status(st, max_age_seconds=300):
                processed_store.add(str(st.get("id")))
    except Exception as e:
        print(f"[{BOT_NAME}] Initial catchup safeguard notice: {e}")

    while True:
        try:
            poll_count += 1
            # 1. 自分宛ての通知（メンション）を直近のものから確認
            notifications = mc.get_notifications(limit=10)
            for notif in reversed(notifications):
                notif_type = notif.get("type")
                if notif_type == "mention":
                    status = notif.get("status")
                    if status:
                        sid = str(status.get("id"))
                        if not sid or processed_store.is_processed(sid):
                            continue
                        if not is_recent_status(status, max_age_seconds=300):
                            processed_store.add(sid)
                            continue
                        await on_status(status, is_notification=True)
                        break  # 一度にすべて拾わず、直前のものを1件ずつ処理

                elif notif_type in ["follow", "follow_request"]:
                    account = notif.get("account", {})
                    acc_id = str(account.get("id"))
                    if acc_id:
                        if notif_type == "follow_request":
                            mc.authorize_follow_request(acc_id)
                        mc.follow_account(acc_id)

            # 2. ホームタイムライン（フォロー中の仲間）の直前投稿のみ確認
            # ※ パブリックTLの無差別監視はセキュリティ上廃止
            home_statuses = mc.get_home_timeline(limit=10)
            seen_ids = set()
            for st in home_statuses:
                sid = str(st.get("id"))
                if not sid or sid in seen_ids or processed_store.is_processed(sid):
                    continue
                seen_ids.add(sid)

                if not is_recent_status(st, max_age_seconds=300):
                    processed_store.add(sid)
                    continue

                txt = MastodonClient.html_to_text(st.get("content", ""))
                if "+TALK" in txt.upper() or mc.is_mentioned(st, my_id=MY_ID, my_username=MY_USERNAME, note_text=txt):
                    await on_status(st, is_notification=False)
                    break  # 一度に大量に処理せず、直前のものを調べて応答

            if poll_count % 20 == 0:
                followed = mc.auto_follow_back()
                if followed > 0:
                    print(f"[{BOT_NAME}] Periodic auto-followback: followed {followed} users.")

        except Exception as e:
            print(f"[{BOT_NAME}] Polling error: {e}")

        await asyncio.sleep(3)

async def main():
    if not mc:
        print("Error: Mastodon client could not be initialized.")
        return
    register_bot(BOT_NAME, mc)
    await resolve_all_bots()
    await asyncio.gather(polling_runner(), teiki())

if __name__ == "__main__":
    asyncio.run(main())
