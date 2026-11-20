"""low(market): a market name inside a sentence - lower case, but TD / TDs / INTs keep their capitals ("3+ passing TDs", not "passing tds";
owner nit 11/18, fixed 11/20)."""
import re
def low(m):
    s = str(m).lower()
    return re.sub(r"\b(td|int)(s?)\b", lambda z: z.group(1).upper() + z.group(2), s)
