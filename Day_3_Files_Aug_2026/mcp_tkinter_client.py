"""
mcp_tkinter_client.py
============================================================
A Tkinter GUI that acts as an MCP CLIENT: it launches
my_mcp_server.py as a subprocess (over the "stdio" transport),
discovers what TOOLS and RESOURCES that server offers, and lets
you call them - all with a real MCP handshake, not a simulation.

Install:
    pip install "mcp[cli]"

Run:
    python mcp_tkinter_client.py
    (make sure my_mcp_server.py and city_data.json are in the
    same folder)

------------------------------------------------------------
WHAT'S HAPPENING UNDER THE HOOD (MCP client lifecycle)
------------------------------------------------------------
1. StdioServerParameters   -> tells the client HOW to launch the
                               server (which command, which script).
2. stdio_client(...)        -> actually spawns the subprocess and
                               opens read/write pipes to it.
3. ClientSession(...)       -> wraps those pipes in the MCP
                               protocol (JSON-RPC messages).
4. session.initialize()     -> the required MCP handshake.
5. session.list_tools()     -> ask the server "what TOOLS do you
                               have?" (name + description + schema)
6. session.list_resources() -> ask the server "what RESOURCES do
                               you expose?" (their URIs)
7. session.call_tool(...)   -> actually invoke a tool with args
8. session.read_resource()  -> actually fetch a resource's data

Because Tkinter's mainloop is synchronous but MCP's client is
async, each button click runs its own short-lived asyncio event
loop (asyncio.run(...)). That means every click launches a fresh
server subprocess - simple to follow for learning purposes. A
production app would keep one session open for the app's lifetime
instead of reconnecting every time.
"""

import asyncio
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_SCRIPT = str(Path(__file__).parent / "my_mcp_server.py")

# How to launch our server: run it with the SAME python interpreter
# that's running this client, passing the server script as the arg.
SERVER_PARAMS = StdioServerParameters(command=sys.executable, args=[SERVER_SCRIPT])


async def mcp_list_tools_and_resources() -> str:
    """Connects, performs the MCP handshake, and asks the server to
    describe itself: 'tools/list' and 'resources/list'."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            resources = await session.list_resources()

            lines = ["TOOLS this server exposes:"]
            for t in tools.tools:
                lines.append(f"  - {t.name}: {t.description}")

            lines.append("\nRESOURCES this server exposes:")
            for r in resources.resources:
                lines.append(f"  - {r.uri}  ({r.name or 'no name'})")

            return "\n".join(lines)


async def mcp_call_get_weather(city: str) -> str:
    """Connects and calls the 'get_weather' TOOL with the raw
    (possibly misspelled) city text - the tool's own fuzzy-matching
    logic (see my_mcp_server.py) handles correction server-side."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("get_weather", {"city": city})
            # Tool results come back as a list of content blocks
            return "\n".join(block.text for block in result.content if hasattr(block, "text"))


async def mcp_read_city_list_resource() -> str:
    """Connects and READS the 'weather://cities' RESOURCE directly -
    no logic, no correction, just raw data exposure. Contrast this
    with call_tool above: a resource read cannot fix typos, only a
    tool (which can run code) can."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.read_resource("weather://cities")
            return "\n".join(c.text for c in result.contents if hasattr(c, "text"))


def run_async(coro):
    """Small helper: run one async MCP call to completion and
    return its result, from inside a normal synchronous Tkinter
    button handler."""
    return asyncio.run(coro)


class MCPClientApp:
    def __init__(self, root):
        self.root = root
        root.title("MCP Client Demo — Tools & Resources")
        root.geometry("720x520")

        pad = {"padx": 10, "pady": 6}

        ttk.Label(root, text="City name:").grid(row=0, column=0, sticky="w", **pad)
        self.city_entry = ttk.Entry(root, width=40)
        self.city_entry.insert(0, "Delih")  # sample typo, on purpose
        self.city_entry.grid(row=0, column=1, sticky="w", **pad)

        btns = ttk.Frame(root)
        btns.grid(row=1, column=0, columnspan=2, pady=8)
        ttk.Button(btns, text="1) Discover tools & resources", command=self.on_discover).pack(side="left", padx=6)
        ttk.Button(btns, text="2) Call TOOL: get_weather", command=self.on_call_tool).pack(side="left", padx=6)
        ttk.Button(btns, text="3) Read RESOURCE: city list", command=self.on_read_resource).pack(side="left", padx=6)

        self.output = scrolledtext.ScrolledText(root, width=86, height=22, wrap="word")
        self.output.grid(row=2, column=0, columnspan=2, padx=10, pady=6)

        note = (
            "Try button 2 with the sample typo 'Delih' already in the box -> the TOOL still "
            "resolves it, because it runs fuzzy-matching logic. Then try button 3, which reads a "
            "RESOURCE (plain data, no logic) - it just hands back whatever is stored, as-is."
        )
        tk.Label(root, text=note, wraplength=700, justify="left", fg="#334155").grid(
            row=3, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 10)
        )

    def _show(self, text):
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, text)

    def on_discover(self):
        self._show("Launching server and asking what it offers...")
        self.root.update_idletasks()
        try:
            result = run_async(mcp_list_tools_and_resources())
        except Exception as e:
            result = f"Error: {e}"
        self._show(result)

    def on_call_tool(self):
        city = self.city_entry.get().strip()
        if not city:
            self._show("Type a city name first.")
            return
        self._show(f"Calling get_weather tool with '{city}'...")
        self.root.update_idletasks()
        try:
            result = run_async(mcp_call_get_weather(city))
        except Exception as e:
            result = f"Error: {e}"
        self._show(result)

    def on_read_resource(self):
        self._show("Reading weather://cities resource...")
        self.root.update_idletasks()
        try:
            result = run_async(mcp_read_city_list_resource())
        except Exception as e:
            result = f"Error: {e}"
        self._show(f"Raw resource contents (our own data file):\n{result}")


if __name__ == "__main__":
    root = tk.Tk()
    app = MCPClientApp(root)
    root.mainloop()
