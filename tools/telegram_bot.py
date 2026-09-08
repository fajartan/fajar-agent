#!/usr/bin/env python3
"""telegram_bot — FAJAR-AGENT via Telegram. Otak & fitur SAMA dgn TUI (agent_turn, tools, memori, skills, sesi).

Bot long-poll (tanpa dependensi). HANYA merespons chat PEMILIK (config telegram_chat) demi keamanan.
Tiap chat = satu sesi (persisten: session id 'tg-<chat>'). Alur BERTAHAP: kirim goal, lalu 'lanjut'.

Setup:
  python3 bb.py llm --setup           # isi llm_api_key/model/provider
  set telegram_token + telegram_chat di ~/.config/bbtui/config.json  (chat id = /start akan menampilkannya)
Jalan:
  python3 bb.py telegram              # atau: bb.py tg

Perintah Telegram: /start /help /new /resume /yolo /model <nama> /memory [cari] /skills /status /stop
Aksi aktif (kirim traffic: recon-deep/nuclei/ext-tools) DITOLAK kecuali /yolo ON. Agent tak pernah submit.
"""
import os, sys, json, time, importlib.util, urllib.request, urllib.parse

D = os.path.dirname(os.path.abspath(__file__))
def _load_llm():
    spec = importlib.util.spec_from_file_location("llm_agent", os.path.join(D, "llm_agent.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
LA = _load_llm()

API = "https://api.telegram.org/bot%s/%s"

def tg(token, method, **params):
    url = API % (token, method)
    data = urllib.parse.urlencode(params).encode()
    try:
        return json.loads(urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=60).read().decode("utf-8", "replace"))
    except Exception as e:
        print("[tg] err", method, e); return {}

def send(token, chat, text):
    for i in range(0, len(text) or 1, 3800):
        tg(token, "sendMessage", chat_id=chat, text=(text[i:i + 3800] or "…"), disable_web_page_preview="true")

def creds():
    c = LA.load_cfg()
    prov = LA.cfg_get(c, "llm_provider", "LLM_PROVIDER", "anthropic").lower()
    model = LA.cfg_get(c, "llm_model", "LLM_MODEL", "claude-sonnet-5" if prov == "anthropic" else "gpt-4o-mini")
    base = LA.cfg_get(c, "llm_base_url", "LLM_BASE_URL", "https://api.openai.com/v1")
    key = LA.cfg_get(c, "llm_api_key", "ANTHROPIC_API_KEY" if prov == "anthropic" else "OPENAI_API_KEY")
    return c, prov, model, base, key

HELP = ("*FAJAR-AGENT* (Telegram)\n"
        "Kirim goal bahasa alami; tiap tahap berhenti di CHECKPOINT — balas *lanjut*.\n\n"
        "/new sesi baru · /resume lanjut sesi · /yolo aktif-traffic on/off\n"
        "/model <nama> ganti model · /memory [cari] · /skills · /status · /stop")

def run_stage(state, chat, text, prov, model, base, key):
    """Jalankan satu tahap agent utk chat ini; kumpulkan output jadi teks Telegram."""
    buf = []
    def emit(kind, body):
        if kind == "llm":
            buf.append(body)
        elif kind == "tool":
            buf.append("⚙ " + body.split(" ", 1)[0])
        elif kind == "result":
            buf.append("  ▸ " + (body[:500] + ("…" if len(body) > 500 else "")).replace("\n", " "))
        else:
            buf.append("⚠ " + body)
    msgs = state.setdefault("messages", LA.new_messages(prov == "anthropic"))
    msgs.append({"role": "user", "content": text})
    LA.agent_turn(msgs, prov, model, key, base, emit, allow_gated=state.get("yolo", False), confirm=None)
    LA.session_save("tg-%s" % chat, msgs)
    return "\n\n".join(buf) or "(tak ada output)"

def main():
    c, prov, model, base, key = creds()
    token = c.get("telegram_token") or os.environ.get("BB_TG_TOKEN")
    owner = str(c.get("telegram_chat") or os.environ.get("BB_TG_CHAT") or "").strip()
    enabled = bool(c.get("telegram_bot_enabled"))
    active_default = bool(c.get("telegram_allow_active"))
    allow = {owner} | {x.strip() for x in str(c.get("telegram_allowlist", "")).split(",") if x.strip()}
    allow.discard("")
    if not token:
        sys.exit("[!] telegram_token kosong. Settings (s) → TELEGRAM BOT, atau env BB_TG_TOKEN.")
    if not key:
        sys.exit("[!] LLM API key kosong. Jalankan: python3 bb.py llm --setup")
    if not enabled:
        sys.exit("[!] bot dimatikan. Aktifkan di Settings (s) → TELEGRAM BOT → 'Aktifkan bot? y', lalu jalankan lagi.")
    me = tg(token, "getMe").get("result", {})
    print(f"[fajar-agent/telegram] bot @{me.get('username','?')} online. owner={owner or '(belum diset)'} "
          f"allowlist={sorted(allow) or '-'} active_default={active_default} model={model}")
    print("    Ctrl+C untuk berhenti.")
    states, offset = {}, None
    while True:
        r = tg(token, "getUpdates", timeout=30, **({"offset": offset} if offset else {}))
        for upd in r.get("result", []):
            offset = upd["update_id"] + 1
            msg = upd.get("message") or upd.get("edited_message") or {}
            chat = str((msg.get("chat") or {}).get("id", "")); text = (msg.get("text") or "").strip()
            if not chat or not text: continue
            # --- otorisasi: owner + allowlist ---
            if not allow:
                send(token, chat, f"Chat id kamu: `{chat}`\nSet Telegram chat id = {chat} di Settings (s) lalu restart bot untuk otorisasi.")
                continue
            if chat not in allow:
                send(token, chat, "⛔ tidak diizinkan."); continue
            st = states.setdefault(chat, {"yolo": active_default})
            low = text.lower()
            try:
                if low in ("/start", "/help"):
                    send(token, chat, HELP)
                elif low == "/new":
                    st["messages"] = LA.new_messages(prov == "anthropic"); send(token, chat, "🆕 sesi baru (memori jangka panjang tetap).")
                elif low == "/resume":
                    m = LA.session_load("tg-%s" % chat)
                    if m: st["messages"] = m; send(token, chat, f"💾 sesi di-resume ({len(m)} pesan). Balas 'lanjut'.")
                    else: send(token, chat, "tak ada sesi tersimpan.")
                elif low == "/yolo":
                    st["yolo"] = not st.get("yolo", False); send(token, chat, ("🟢 YOLO ON — aksi aktif diizinkan." if st["yolo"] else "🔴 YOLO OFF — aksi aktif ditolak."))
                elif low.startswith("/model"):
                    p = text.split(None, 1)
                    if len(p) > 1:
                        c2 = LA.load_cfg(); c2["llm_model"] = p[1].strip()
                        json.dump(c2, open(LA.CFG, "w", encoding="utf-8"), indent=1); send(token, chat, f"model → {p[1].strip()} (restart bot bila perlu).")
                    else:
                        send(token, chat, "model sekarang: " + model + "\nmodel tersedia:\n" + "\n".join(LA.fetch_models(prov, key, base)[:40]))
                elif low.startswith("/memory"):
                    q = text.split(None, 1); out = LA.mem_search(q[1]) if len(q) > 1 else LA.mem_list()
                    send(token, chat, "🧠 " + out[:3500])
                elif low == "/skills":
                    send(token, chat, LA.t_list_skills()[:3500])
                elif low == "/status":
                    send(token, chat, f"model={model} provider={prov} yolo={'ON' if st.get('yolo') else 'off'} "
                                      f"pesan={len(st.get('messages') or [])} tools={len(LA.TOOLS)}")
                elif low == "/stop":
                    send(token, chat, "ok, berhenti. (kirim goal baru kapan saja)")
                else:
                    send(token, chat, "⏳ memproses…")
                    reply = run_stage(st, chat, text, prov, model, base, key)
                    send(token, chat, reply)
            except Exception as e:
                send(token, chat, f"⚠ error: {e}")
        time.sleep(1)

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\n[fajar-agent/telegram] stop.")
