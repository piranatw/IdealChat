# IdealChat (Python raw TCP sockets + web UI)

Files: `server.py` (server), `protocol.py` (hand-written HTTP + WebSocket on raw sockets), `web/` (the client: `index.html`, `app.js`, `style.css`). Python 3.8+ stdlib only, nothing to install. The client runs in any modern browser.

**Live deployment (Render): https://idealchat.onrender.com/** - open it on two different computers to chat. It is on the free tier, so it sleeps after 15 minutes without traffic; the first load can take 30-60 s.

## Run
```
python server.py --port 5000          # on the server machine (LAN PC or cloud VM)
```
Then open `http://localhost:5000` in a browser (or `http://<server-ip>:5000` from another computer), type a unique name and press Connect. Open the page on a second computer, with a different name, to chat.

Cloud: open inbound TCP 5000 in the VM firewall/security group, then clients browse to `http://<public-ip>:5000`.
LAN fallback: server's IPv4 from `ipconfig`; allow Python through Windows Firewall.

### Gemini API key (AI chatbot)
The AI feature calls the Google Gemini API, so **the computer that runs `server.py` must use its own API key**. The key is read from the `GEMINI_API_KEY` environment variable. Only the server computer needs it; the clients (browsers) never see it. Never write the key into the code or commit it to git. Get a free key at https://aistudio.google.com.

Set the key and start the server **in the same terminal window** (the variable only lasts for that terminal):

Mac / Linux (zsh or bash):
```
export GEMINI_API_KEY="your-key-here"
python3 server.py --port 5000
```

Windows PowerShell:
```
$env:GEMINI_API_KEY = "your-key-here"
python server.py --port 5000
```

Windows cmd:
```
set GEMINI_API_KEY=your-key-here
python server.py --port 5000
```

Without a key the server still runs, but the bot answers "not configured". On the cloud the key is set as an environment variable in the hosting dashboard (see below).

### Deploy on Render (free, no credit card)
Our deployed website: **https://idealchat.onrender.com/**

Render runs `server.py` from this GitHub repo and gives it an HTTPS URL. The browser client switches to `wss://` by itself on HTTPS, so no code change is needed.

1. Push the repo to GitHub (never commit the API key; `.gitignore` already excludes caches and `.env`).
2. On https://render.com choose **New -> Web Service**, connect the GitHub repo.
3. Settings: Runtime **Python 3**, Build command `echo ok` (nothing to install), Start command `python server.py --port $PORT`, Instance type **Free**.
4. Under **Environment** add `GEMINI_API_KEY` = your key (optional: `GEMINI_MODEL`).
5. After the deploy finishes, open the `https://<name>.onrender.com` URL on two different computers and chat.

Free-tier notes: the service sleeps after 15 minutes without traffic and takes about 30-60 s to wake up, and users/groups/messages live in memory, so they are lost when it sleeps or restarts. Open the URL a few minutes before a demo. The browser sends a small `ping` message every 25 s so the connection is not closed as idle and counts as activity.

## Architecture (R1)
```
 Browser A (PC 1) --TCP--+
                         +-- server.py (cloud VM / 3rd PC, port 5000)
 Browser B (PC 2) --TCP--+
```
Star topology: all messages go client -> server -> recipients. One port serves both the web page (HTTP) and the chat (WebSocket). The server holds `clients` (name -> connection), `groups` (group -> members) and `group_history` (group -> last 500 messages).

## Protocols (what / why / how)
- **TCP** - reliable, ordered byte stream; every client has one persistent connection, opened with `socket.SOCK_STREAM` (`server.py main()`).
- **IP** - addresses and routes between the PCs and the server; browsers connect to the server's (public) IP.
- **Port 5000** - identifies the chat server process on the host (`bind`).
- **HTTP** - a browser can only load a web page and open a WebSocket through HTTP, so the first request on each connection is plain HTTP: `GET /` returns `index.html`, `app.js`, `style.css` (`serve_static`).
- **WebSocket (RFC 6455)** - a browser cannot open a raw TCP socket. WebSocket is the standard way for a browser to keep a TCP connection open and exchange messages in both directions, so the server can push messages instantly instead of the client polling. It starts as an HTTP request with `Upgrade: websocket`; the server answers `101 Switching Protocols` and from then on both sides send frames. We implemented the handshake and the frame format ourselves in `protocol.py` (`accept_websocket`, `WSConn.send/recv`) using only the `socket` module - no HTTP or WebSocket library.
- **Application messages** - each chat message is one JSON object in one WebSocket text frame (table below).

## Message types
| type | direction | fields | req |
|---|---|---|---|
| `login` / `login_ok` / `login_error` | C->S / S->C | name / reason | R3 |
| `users` | S->C (broadcast on join/leave) | users[] | R4 |
| `pm` | C->S (`to`,`text`); S->C to receiver + sender echo (`from`,`to`,`text`,`ts`) | | R7 |
| `create_group` | C->S | group (creator is the only member) | R8 |
| `list_groups` / `groups` | C->S / S->C (also broadcast on change) | groups[{name, members}] | R9 |
| `join_group` | C->S | group (only adds the requester) | R10 |
| `group_msg` | C->S (`group`,`text`); S->C members only | | R11 |
| `group_history` | S->C to the joiner only, right after `join_group` | group, messages[] (latest 500) | R9/R11 |
| `error` | S->C | text | |
| `edit_msg` | C->S | id, text (owner only) | bonus |
| `delete_msg` | C->S | id (owner only) | bonus |
| `react` | C->S | id, emoji (toggles our reaction) | bonus |
| `msg_update` | S->C to everyone who can see the message | full message: id, kind, text, edited, deleted, reactions | bonus |
| `typing` | C->S, relayed S->C to the other people in the chat | kind (`pm`/`group`), to / group, from, state | bonus |

Every `pm` / `group_msg` now also carries `id`, `kind`, `edited`, `deleted`, `reactions`.

## Requirement map
R1/R2: `server.py main()` (`socket/bind/listen/accept`), `protocol.py` (`recv/sendall` + WebSocket frames), `web/app.js connect()`. R3: `login()` in server.py, login form in `web/index.html`. R4: `broadcast_users`, `renderUsers`. R5/R6: `ensureRoom` in `web/app.js` (one tab per chat, each with a chat window + chat box). R7-R11: `handle()` in server.py, `renderGroups`/`ensureRoom` in `web/app.js`.

Bonus features: server side in `handle()` in `server.py` (`edit_msg` / `delete_msg` / `react` / `typing`, helpers `new_record`, `snap`, `can_see`, `audience`); client side in `renderMsg`, `startEdit`, `showTyping` in `web/app.js`.

Message text is always inserted into the page with `textContent` (never as HTML), so a message such as `<script>` is displayed literally.


## Additional Requirement 
1. Non-AI features :
  - Typing indicator: a new typing message type, shown in the room as "bob is typing...".
  - Emoji reactions on messages: allow user to add emoji reactions to message.
  - Message edit/delete

Reason of picking this 3 features is they're visible in a demo, and each one need new socket messages which fits the "socket programming" theme.

2. AI feature: chatbot (Google Gemini), code in `bot.py` (`ask_gemini`) and `start_bot` / `bot_answer` in `server.py`.
  - **Private chat with the bot:** click `Bot (AI)` in the online list; every message gets an answer, and the bot remembers the last 10 turns. Only the asker sees it.
  - **In a group:** type `@bot <question>`; the answer is posted to the whole group. The bot is given the group's last 15 messages as context, so `@bot summarize this chat` works.
  - The question and the answer travel as normal `pm` / `group_msg` messages over our own sockets (R2 is unchanged); only the server talks to Gemini (HTTPS REST, `urllib`). While waiting, the bot shows "Bot is typing..." using the typing indicator.
  - Safety: the name `Bot` is reserved at login, one request per user every 3 s, at most 3 Gemini calls at once, errors (no key / busy / no network) are posted as a bot message instead of failing silently. Needs `GEMINI_API_KEY` on the server computer (see Run). The model can be changed with `GEMINI_MODEL`.
