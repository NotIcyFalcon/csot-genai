import os
import json
import asyncio
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
from typing import Any
import aiohttp
import httpx
from openai import AsyncOpenAI
from dotenv import load_dotenv
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll, Container
from textual.widgets import Header, Input, Static, RichLog, Footer
from textual.binding import Binding
from rich.markdown import Markdown
from mcp import ClientSession
from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken

load_dotenv()

openRouterClient = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"]
)

SERPER_KEY = os.environ.get("SERPER_API_KEY", "")
ALPHAXIV_URL = "https://api.alphaxiv.org/mcp/v1"
REDIRECT_URL = "http://localhost:8765/callback"
TOKEN_CACHE = ".alphatoken.json"

systemState = {
    "history": [],
    "exchangeCount": 0,
    "maxExchanges": 12,
    "mcpSchemas": [],
    "mcpToolNames": []
}

appContext = None

basePersona = """You are an advanced analysis engine. Keep your responses highly technical and strictly fact-based.
Do not use conversational filler. Be direct and objective."""

nature = "You are a helpful AI assistant who blends a friendly, welcoming tone with professional reliability. Whenever a new conversation starts, warmly introduce yourself and politely ask the user how you can support them today. You must communicate clearly and efficiently. Keep the interaction focused, polite, and perfectly paced."

searchConstraints = """CRITICAL PROTOCOL:
You possess tools to search and fetch web data. You MUST ONLY report information gathered from these tools.
If data is missing, state it is missing. Do not extrapolate facts."""

class DiskTokenStore(TokenStorage):
    def __init__(self):
        self.tokens = None
        self.client_info = None
        if os.path.exists(TOKEN_CACHE):
            try:
                data = json.loads(open(TOKEN_CACHE, "r").read())
                if "tokens" in data:
                    self.tokens = OAuthToken.model_validate(data["tokens"])
                if "client_info" in data:
                    self.client_info = OAuthClientInformationFull.model_validate(data["client_info"])
            except Exception:
                pass

    def _flush(self):
        dump = {}
        if self.tokens:
            dump["tokens"] = self.tokens.model_dump(mode="json")
        if self.client_info:
            dump["client_info"] = self.client_info.model_dump(mode="json")
        with open(TOKEN_CACHE, "w") as f:
            f.write(json.dumps(dump))

    async def get_tokens(self): return self.tokens
    async def set_tokens(self, t): self.tokens = t; self._flush()
    async def get_client_info(self): return self.client_info
    async def set_client_info(self, c): self.client_info = c; self._flush()

async def launchBrowser(url: str):
    if appContext:
        appContext.writeSystemLog("[dim]Opening browser for OAuth authentication...[/dim]")
    webbrowser.open(url)

async def awaitAuthCallback():
    authCode = None
    returnedState = None

    class SrvHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal authCode, returnedState
            queryParts = parse_qs(urlparse(self.path).query)
            if "code" in queryParts:
                authCode = queryParts["code"][0]
            if "state" in queryParts:
                returnedState = queryParts["state"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Authorized! Return to the terminal.</h1></body></html>")
            
        def log_message(self, format, *args):
            pass

    httpSrv = HTTPServer(("localhost", 8765), SrvHandler)
    httpSrv.timeout = 120
    await asyncio.to_thread(httpSrv.handle_request)
    httpSrv.server_close()
    if not authCode:
        raise RuntimeError("No code received")
    return authCode, returnedState

oauthProvider = OAuthClientProvider(
    server_url=ALPHAXIV_URL,
    client_metadata=OAuthClientMetadata(
        client_name="Chatbot V2 MCP",
        redirect_uris=[REDIRECT_URL],
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        scope="read",
    ),
    storage=DiskTokenStore(),
    redirect_handler=launchBrowser,
    callback_handler=awaitAuthCallback,
)

async def searchWeb(query: str):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
                json={"q": query, "num": 5},
                timeout=8
            ) as r:
                r.raise_for_status()
                blob = await r.json()
                lines = []
                for x, i in enumerate(blob.get("organic", [])):
                    lines.append(f"Result {x+1}: {i.get('title')} | URL: {i.get('link')} | Snippet: {i.get('snippet')}")
                return "\n".join(lines)
    except Exception as e:
        return f"Search Error: {e}"

async def fetchWebPage(url: str):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://r.jina.ai/{url}", timeout=15) as r:
                r.raise_for_status()
                text = await r.text()
                return text[:3500]
    except Exception as e:
        return f"Fetch Error: {e}"

async def loadAlphaXivTools():
    try:
        async with httpx.AsyncClient(auth=oauthProvider, follow_redirects=True, timeout=60) as http:
            async with streamable_http_client(ALPHAXIV_URL, http_client=http) as (r, w, _):
                async with ClientSession(r, w) as sess:
                    await sess.initialize()
                    payload = await sess.list_tools()
                    output = []
                    for t in payload.tools:
                        output.append({
                            "type": "function",
                            "function": {
                                "name": t.name,
                                "description": t.description,
                                "parameters": t.inputSchema
                            }
                        })
                    return output
    except Exception as e:
        if appContext:
            appContext.writeSystemLog(f"[red]AlphaXiv Load Error: {e}[/red]")
        return []

async def invokeMcpTool(name: str, arguments: dict):
    try:
        async with httpx.AsyncClient(auth=oauthProvider, follow_redirects=True, timeout=60) as http:
            async with streamable_http_client(ALPHAXIV_URL, http_client=http) as (r, w, _):
                async with ClientSession(r, w) as sess:
                    await sess.initialize()
                    res = await sess.call_tool(name, arguments=arguments)
                    if res.content and res.content[0].type == "text":
                        return res.content[0].text
                    return "Execution finished with no text output."
    except Exception as e:
        return f"MCP execution failed: {e}"

searchFuncDef = {
    "type": "function",
    "function": {
        "name": "searchWeb",
        "description": "Performs a deep web search to find primary source links. Do not rely entirely on the snippets returned.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search string optimized for search engines."}},
            "required": ["query"]
        }
    }
}

fetchFuncDef = {
    "type": "function",
    "function": {
        "name": "fetchWebPage",
        "description": "Pulls markdown text from a single URL. Content is truncated at 3500 characters.",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "The exact URL to scrape."}},
            "required": ["url"]
        }
    }
}

async def initiateEngine(personaStr):
    systemState["history"] = [{"role": "system", "content": personaStr + "\n" + searchConstraints}]
    appContext.writeSystemLog("[green]Initializing AlphaXiv connection...[/green]")
    systemState["mcpSchemas"] = await loadAlphaXivTools()
    if systemState["mcpSchemas"]:
        systemState["mcpToolNames"] = [s["function"]["name"] for s in systemState["mcpSchemas"]]
        appContext.writeSystemLog(f"[cyan]Loaded {len(systemState['mcpToolNames'])} MCP Tools.[/cyan]")
    
    appContext.writeChatBubble("[italic #999999]System ready. GPT-OSS-120B online.[/italic #999999]", role="system")

async def forceSummarize():
    appContext.writeSystemLog("[yellow]Memory threshold reached. Summarizing context.[/yellow]")
    summaryPrompt = "Summarize the key factual takeaways from the entire conversation above into a concise, detailed technical report. Ignore pleasantries."
    systemState["history"].append({"role": "user", "content": summaryPrompt})
    
    try:
        resp = await openRouterClient.chat.completions.create(
            model="openai/gpt-oss-120b:free",
            messages=systemState["history"],
            stream=False
        )
        report = resp.choices[0].message.content or "No summary."
        systemState["history"] = [
            {"role": "system", "content": basePersona + "\n" + searchConstraints},
            {"role": "assistant", "content": f"Previous session summary:\n{report}"}
        ]
        systemState["exchangeCount"] = 0
        appContext.writeChatBubble("[italic #999999]Conversation memory compressed.[/italic #999999]", role="system")
    except Exception as e:
        appContext.writeSystemLog(f"[red]Summarization failed: {e}[/red]")

async def processRequest(prompt: str, is_exit: bool = False):
    if prompt:
        systemState["history"].append({"role": "user", "content": prompt})
    appContext.writeSystemLog("[dim]Querying primary model...[/dim]")
    
    toolsToPass = [searchFuncDef, fetchFuncDef] + systemState["mcpSchemas"]
    
    try:
        while True:
            streamReq = await openRouterClient.chat.completions.create(
                model="openai/gpt-oss-120b:free",
                messages=systemState["history"],
                tools=toolsToPass,
                tool_choice="auto",
                stream=True
            )
            
            uiScroll = appContext.query_one("#chatScrollArea", VerticalScroll)
            chatElem = None
            rawOutput = ""
            activeTools = []
            
            lastUpdateLen = 0
            async for dataChunk in streamReq:
                if not dataChunk.choices: continue
                chunkObj = dataChunk.choices[0].delta
                
                if chunkObj.tool_calls:
                    for t in chunkObj.tool_calls:
                        while len(activeTools) <= t.index:
                            activeTools.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                        if t.id: activeTools[t.index]["id"] += t.id
                        if t.function and t.function.name: activeTools[t.index]["function"]["name"] += t.function.name
                        if t.function and t.function.arguments: activeTools[t.index]["function"]["arguments"] += t.function.arguments
                        
                if chunkObj.content:
                    if not chatElem:
                        chatElem = ChatItem(Markdown("**Assistant:** "), mode="agent")
                        await uiScroll.mount(chatElem)
                    rawOutput += chunkObj.content
                    if len(rawOutput) - lastUpdateLen > 15 or chunkObj.content.endswith("\n"):
                        chatElem.query(Static).first().update(Markdown(f"**Assistant:** {rawOutput}"))
                        lastUpdateLen = len(rawOutput)
                        uiScroll.scroll_end(animate=False)
            if rawOutput and chatElem:
                chatElem.query(Static).first().update(Markdown(f"**Assistant:** {rawOutput}"))
                uiScroll.scroll_end(animate=False)
            
            if activeTools:
                systemState["history"].append({
                    "role": "assistant", 
                    "content": None, 
                    "tool_calls": activeTools
                })
                
                for t in activeTools:
                    fName = t["function"]["name"]
                    fArgsRaw = t["function"]["arguments"]
                    try:
                        fArgs = json.loads(fArgsRaw)
                    except:
                        fArgs = {}
                    
                    appContext.writeSystemLog(f"[bold magenta]INVOKING:[/bold magenta] {fName}")
                    if fArgs:
                        appContext.writeSystemLog(f"Args: {json.dumps(fArgs)}")
                        
                    resText = ""
                    if fName == "searchWeb":
                        resText = await searchWeb(fArgs.get("query", ""))
                    elif fName == "fetchWebPage":
                        resText = await fetchWebPage(fArgs.get("url", ""))
                    elif fName in systemState["mcpToolNames"]:
                        resText = await invokeMcpTool(fName, fArgs)
                        
                    systemState["history"].append({
                        "role": "tool",
                        "tool_call_id": t["id"],
                        "name": fName,
                        "content": str(resText)
                    })
                continue
            else:
                if rawOutput:
                    systemState["history"].append({"role": "assistant", "content": rawOutput})
                uiScroll.scroll_end(animate=False)
                break
                
        systemState["exchangeCount"] += 1
        
        if systemState["exchangeCount"] >= systemState["maxExchanges"]:
            await forceSummarize()
            
    except Exception as ex:
        appContext.writeChatBubble("API Error occurred during processing.", role="agent")
        appContext.writeSystemLog(f"[red]Exception: {ex}[/red]")

class ChatItem(Static):
    def __init__(self, contentPayload: Any, mode: str = "agent", **kwargs):
        super().__init__(**kwargs)
        self.mode = mode
        self.contentPayload = contentPayload

    def compose(self) -> ComposeResult:
        yield Static(self.contentPayload)

    def on_mount(self) -> None:
        self.add_class(f"bubble-{self.mode}")

class TerminalUI(App):
    CSS = """
    #wrapper { layout: horizontal; height: 100%; width: 100%; }
    #chatZone { width: 65%; height: 100%; border-right: solid #333333; background: #0c0c0c; }
    #chatScrollArea { height: 1fr; padding: 1; }
    #inputZone { height: 3; dock: bottom; margin: 1; background: #1a1a1a; border: solid #555555; }
    #infoZone { width: 35%; height: 100%; background: #050505; }
    #systemConsole { height: 1fr; padding: 1; color: #a3a3a3; }

    .bubble-agent { background: #121f2b; color: #cdd6f4; border: solid #1e3b5e; padding: 1 2; margin: 1 6 1 0; }
    .bubble-user { background: #1c261e; color: #a6e3a1; border: solid #2f5235; padding: 1 2; margin: 1 0 1 6; text-align: right; }
    .bubble-system { background: transparent; color: #6c7086; text-align: center; text-style: italic; margin: 1 0; }

    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+k", "clear_sys", "Clear System Panel", priority=True),
        Binding("ctrl+l", "clear_msgs", "Clear Chat Area", priority=True),
        Binding("ctrl+s", "summarize", "Summarize", priority=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="wrapper"):
            with Vertical(id="chatZone"):
                yield VerticalScroll(id="chatScrollArea")
                yield Input(placeholder="Type message...", id="inputZone")
            with Vertical(id="infoZone"):
                yield RichLog(id="systemConsole", wrap=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        global appContext
        appContext = self
        self.query_one(Input).focus()
        
        systemState["maxExchanges"] = 12

        async def startupSequence():
            await initiateEngine(nature)
            await processRequest("System: Generate a warm, casual greeting introducing yourself as an AI assistant ready to help.")
            
        asyncio.create_task(startupSequence())

    async def action_quit(self) -> None:
        self.writeSystemLog("[red]Exiting. Generating sign-off...[/red]")
        systemState["history"].append({"role": "system", "content": "The user is exiting the application. Generate a brief 1-2 sentence polite goodbye message."})
        await processRequest("", is_exit=True)
        self.exit()

    def writeChatBubble(self, text: str, role: str) -> None:
        scroller = self.query_one("#chatScrollArea", VerticalScroll)
        if role == "user":
            elem = ChatItem(Markdown(f"**User:** {text}"), mode="user")
        elif role == "system":
            elem = ChatItem(text, mode="system")
        else:
            elem = ChatItem(Markdown(f"**Assistant:** {text}"), mode="agent")
        scroller.mount(elem)
        scroller.scroll_end(animate=False)

    def writeSystemLog(self, text: str) -> None:
        self.query_one("#systemConsole", RichLog).write(text)

    def action_clear_sys(self) -> None:
        self.query_one("#systemConsole", RichLog).clear()

    def action_clear_msgs(self) -> None:
        self.query_one("#chatScrollArea", VerticalScroll).remove_children()

    async def action_summarize(self) -> None:
        self.writeSystemLog("[blue]Manual summarization triggered.[/blue]")
        asyncio.create_task(forceSummarize())

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        msg = event.value
        if not msg.strip(): return
        event.input.value = ""
        self.writeChatBubble(msg, "user")
        asyncio.create_task(processRequest(msg))

if __name__ == "__main__":
    TerminalUI().run()
