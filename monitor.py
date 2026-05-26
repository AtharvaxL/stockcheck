import requests, os, smtplib, json
from email.message import EmailMessage
from twilio.rest import Client

# ── Credentials come from GitHub Secrets ──────────────────
ATICKET       = os.environ["ATICKET"]
SESSION_TOKEN = os.environ["SESSION_TOKEN"]
EMAIL_FROM    = os.environ["EMAIL_FROM"]
EMAIL_PASSWORD= os.environ["EMAIL_PASSWORD"]
EMAIL_TO      = os.environ["EMAIL_TO"]
TWILIO_SID    = os.environ["TWILIO_SID"]
TWILIO_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]
CALL_FROM     = os.environ["CALL_FROM"]   # your Twilio number e.g. +14155551234
CALL_TO       = os.environ["CALL_TO"]     # your personal number e.g. +919999999999

# ── API Config ────────────────────────────────────────────
API_URL = "https://rog.asus.com/elite/api/v2/RewardList"
PARAMS  = {"aticket": ATICKET, "WebsiteCode": "in", "systemCode": "rog"}
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
COOKIES = {"aticket": ATICKET, "token": SESSION_TOKEN}

# ── Items to ignore ───────────────────────────────────────
IGNORED = [
    "wallpaper", "animated", "evangelion", "mechatronics",
    "pinball", "prism", "retro", "psychedelic", "mechanize"
]

# ── State file (tracks last known status between runs) ────
STATE_FILE = "last_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def is_ignored(name):
    return any(k.lower() in name.lower() for k in IGNORED)

def send_email(item):
    try:
        msg = EmailMessage()
        msg["Subject"] = f"IN STOCK: {item}"
        msg["From"]    = EMAIL_FROM
        msg["To"]      = EMAIL_TO
        msg.set_content(
            f"'{item}' is now IN STOCK on ASUS ROG Elite!\n\n"
            f"https://rog.asus.com/in/event/rog-elite-program/rewards/"
        )
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(EMAIL_FROM, EMAIL_PASSWORD)
            s.send_message(msg)
        print(f"  [EMAIL] Sent for: {item}")
    except Exception as e:
        print(f"  [EMAIL] Failed: {e}")

def send_call(item):
    try:
        c = Client(TWILIO_SID, TWILIO_TOKEN)
        c.calls.create(
            twiml=(
                f"<Response>"
                f"<Say voice='alice'>Alert! {item} is now in stock on the ASUS ROG Elite store.</Say>"
                f"<Pause length='1'/>"
                f"<Say voice='alice'>Repeating: {item} is now in stock.</Say>"
                f"</Response>"
            ),
            to=CALL_TO,
            from_=CALL_FROM
        )
        print(f"  [CALL]  Placed for: {item}")
    except Exception as e:
        print(f"  [CALL]  Failed: {e}")

# ── Main ──────────────────────────────────────────────────
def main():
    print("Checking stock...")
    last = load_state()

    try:
        resp = requests.get(API_URL, params=PARAMS, headers=HEADERS,
                            cookies=COOKIES, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Request failed: {e}")
        return

    if data.get("Status") != "0":
        print(f"API error: {data.get('Message')}")
        return

    new_state = {}
    for item in data.get("Result", {}).get("Obj", []):
        name   = item.get("RewardName", "").strip()
        status = item.get("Status")
        if not name or is_ignored(name):
            continue

        new_state[name] = status
        prev = last.get(name)

        if status == 1 and prev != 1:
            # Just came IN STOCK
            print(f"*** IN STOCK: {name} ***")
            send_email(name)
            send_call(name)
        elif status == 3 and prev != 3:
            print(f"Out of stock: {name}")
        elif prev is None:
            print(f"New item detected: {name} — status {status}")

    save_state(new_state)

    # Commit updated state back to repo so next run has it
    os.system('git config user.email "stockbot@users.noreply.github.com"')
    os.system('git config user.name "Stock Bot"')
    os.system('git add last_state.json')
    os.system('git diff --cached --quiet || git commit -m "chore: update state"')
    os.system('git push')
    print("Done.")

if __name__ == "__main__":
    main()
