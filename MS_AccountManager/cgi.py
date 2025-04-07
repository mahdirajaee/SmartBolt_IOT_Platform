"""
Compatibility shim for the removed cgi module in Python 3.13.
This provides just enough functionality for CherryPy to work.
"""

def parse_header(line):
    """Parse a Content-type like header.
    
    Return the main content-type and a dictionary of parameters.
    This replaces the removed cgi.parse_header function.
    """
    parts = line.split(';')
    key = parts[0].strip()
    pdict = {}
    
    for p in parts[1:]:
        if '=' not in p:
            continue
        name, value = p.split('=', 1)
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        pdict[name] = value
    
    return key, pdict