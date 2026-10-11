"""
my_mcp_server.py
============================================================
A REAL, RUNNABLE MCP SERVER (not a simulation) that shows:

  1) How to create a TOOL          -> @mcp.tool()
  2) How to create a RESOURCE      -> @mcp.resource("uri")
  3) How to import data from YOUR OWN resource (a local JSON
     file you own, instead of a third-party API) and serve it
     through MCP.

Install:
    pip install "mcp[cli]"

Run standalone (for a quick sanity check, prints protocol
messages if you speak MCP over stdin/stdout manually - normally
you don't run it directly, an MCP CLIENT launches it for you):
    python my_mcp_server.py

Test it easily with the official inspector:
    npx @modelcontextprotocol/inspector python my_mcp_server.py

Or drive it from our own Tkinter client:
    python mcp_tkinter_client.py
============================================================
CONCEPT RECAP
------------------------------------------------------------
TOOL      = an ACTION the model/client can invoke. It takes
            arguments, runs code (can include logic, branching,
            fuzzy matching, calling other APIs, etc.) and returns
            a result. Defined here with the @mcp.tool() decorator.

RESOURCE  = DATA the model/client can read, identified by a URI
            (like a filename or web address, e.g.
            "weather://cities"). Resources are meant to be closer
            to a read-only "GET" - they hand back data, not
            perform actions. Defined here with @mcp.resource(uri).

Both a tool and a resource in this file pull from the SAME
local file (city_data.json) - "our own resource" - instead of
calling any external weather API. That's the "import data from
our own resources" part of the demo.
"""

import json
import difflib
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# ------------------------------------------------------------------
# 1) IMPORT DATA FROM OUR OWN RESOURCE
#    Any local data store works here: JSON, CSV, SQLite, a folder
#    of files, a database connection, etc. We use a JSON file that
#    ships next to this script, so the whole demo is self-contained.
# ------------------------------------------------------------------
DATA_FILE = Path(__file__).parent / "city_data.json"


def load_city_data() -> dict:
    """Reads OUR OWN data file fresh each time it's needed.
    Swap this for a DB query / CSV read / cloud file fetch and
    every tool + resource below keeps working unchanged."""
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------
# Create the MCP server instance. The name shows up in MCP clients
# (Claude Desktop, our Tkinter client, the MCP Inspector, etc.)
# ------------------------------------------------------------------
mcp = FastMCP("Own-Data Weather Server")


# ------------------------------------------------------------------
# 2) A RESOURCE - plain data, read-only, addressed by a URI.
#    A client can "read" this the same way it would read a file.
#    No arguments here -> a static resource.
# ------------------------------------------------------------------
@mcp.resource("weather://cities")
def list_cities() -> str:
    """Expose the list of city names available in our own data file.
    This is pure data exposure - no decision-making, no side effects."""
    data = load_city_data()
    return json.dumps(sorted(data.keys()))


# ------------------------------------------------------------------
# 3) A PARAMETERIZED RESOURCE - the {city} in the URI becomes a
#    function argument automatically. Still just data lookup, no
#    correction/fuzzy logic - if the key doesn't exist exactly,
#    it simply won't be found (same rigidity as a plain API).
# ------------------------------------------------------------------
@mcp.resource("weather://city/{city}")
def get_city_record(city: str) -> str:
    """Return the raw stored record for an EXACT city name."""
    data = load_city_data()
    if city in data:
        return json.dumps(data[city])
    return json.dumps({"error": f"No exact record for '{city}'"})


# ------------------------------------------------------------------
# 4) A TOOL - an action with logic. Unlike the resource above, this
#    can reason: it fuzzy-matches misspelled input against our own
#    data before answering, which is why MCP tools still work with
#    typos while a raw API/resource lookup does not.
# ------------------------------------------------------------------
@mcp.tool()
def get_weather(city: str) -> str:
    """Get current weather for a city from our own local dataset.

    Unlike a raw API call, this TOOL contains logic: if the exact
    spelling isn't found, it looks for the closest match among the
    known city names (difflib) before giving up - so typos like
    'Delih' or 'Mumbaii' still resolve correctly.
    """
    data = load_city_data()

    if city in data:
        matched = city
    else:
        close = difflib.get_close_matches(city, data.keys(), n=1, cutoff=0.6)
        if not close:
            return f"No weather data found for '{city}'."
        matched = close[0]

    record = data[matched]
    note = "" if matched == city else f" (matched from your input '{city}')"
    return (f"{matched}{note}: {record['temp_c']}°C, "
            f"{record['condition']}, humidity {record['humidity']}%")


@mcp.tool()
def list_available_cities() -> str:
    """A second, simple tool: just list what cities we have data for."""
    return ", ".join(sorted(load_city_data().keys()))


# ------------------------------------------------------------------
# Start the server. "stdio" transport = the server talks to its
# client over stdin/stdout, which is how an MCP client (Claude
# Desktop, our Tkinter app, the Inspector) launches and talks to it
# as a subprocess. This is the most common transport for local tools.
# ------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run(transport="stdio")
