import requests, json, sys, time, os

BASE = "http://localhost:8000/api"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tester_state.json")

def load():
    try:
        return json.load(open(STATE_FILE))
    except Exception:
        return {}

def save(st):
    json.dump(st, open(STATE_FILE, "w"))

def login():
    r = requests.post(f"{BASE}/auth/login", json={"email":"clientedemo@test.com","password":"demo123"})
    r.raise_for_status()
    tok = r.json()["access_token"]
    st = load(); st["token"] = tok; save(st)
    return tok

def hdr():
    return {"Authorization": "Bearer " + load()["token"]}

def start():
    time.sleep(4)
    r = requests.post(f"{BASE}/chatbot/start", headers=hdr())
    print("START:", r.status_code, json.dumps(r.json(), ensure_ascii=False))
    sid = r.json()["session_id"]
    st = load(); st["sid"] = sid; save(st)
    return sid

def configure(**kw):
    sid = load()["sid"]
    r = requests.post(f"{BASE}/chatbot/configure", params={"session_id": sid}, json=kw, headers=hdr())
    print("CONFIGURE:", r.status_code)
    print(json.dumps(r.json(), ensure_ascii=False, indent=2))

def msg(text):
    sid = load()["sid"]
    r = requests.post(f"{BASE}/chatbot/message", json={"session_id": sid, "message": text}, headers=hdr())
    print("="*80)
    print("YO:", text)
    print("HTTP:", r.status_code)
    try:
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))
    except Exception:
        print(r.text[:2000])

def complete():
    sid = load()["sid"]
    r = requests.post(f"{BASE}/chatbot/complete-meal", params={"session_id": sid}, headers=hdr())
    print("COMPLETE-MEAL:", r.status_code)
    print(json.dumps(r.json(), ensure_ascii=False, indent=2))

def suggest():
    sid = load()["sid"]
    r = requests.post(f"{BASE}/chatbot/suggest-foods", params={"session_id": sid}, headers=hdr())
    print("SUGGEST:", r.status_code)
    print(json.dumps(r.json(), ensure_ascii=False, indent=2))

def summary():
    sid = load()["sid"]
    r = requests.get(f"{BASE}/chatbot/summary", params={"session_id": sid}, headers=hdr())
    print("SUMMARY:", r.status_code)
    print(json.dumps(r.json(), ensure_ascii=False, indent=2))
