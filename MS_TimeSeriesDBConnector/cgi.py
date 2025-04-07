"""
Compatibility module for CherryPy to work with Python 3.13+
The cgi module was deprecated in Python 3.10 and removed in Python 3.13.
This module provides the necessary functions that CherryPy requires.
"""

def parse_header(line):
    """Parse a Content-type like header.
    
    Return the main content-type and a dictionary of parameters.
    """
    parts = []
    for i, char in enumerate(line):
        if char == ';':
            parts.append(line[:i].strip())
            line = line[i+1:]
            break
    if not parts:
        parts.append(line.strip())
        line = ''
    
    parts.extend([p.strip() for p in line.split(';') if p.strip()])
    
    key = parts.pop(0).lower()
    pdict = {}
    
    for p in parts:
        if '=' not in p:
            pdict[p] = ''
            continue
        
        name, value = p.split('=', 1)
        name = name.strip().lower()
        value = value.strip()
        
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
            value = value.replace('\\\\', '\\').replace('\\"', '"')
        
        pdict[name] = value
    
    return key, pdict

def parse_multipart(fp, pdict):
    """Mock function to satisfy imports but not meant to be used"""
    raise NotImplementedError(
        "The cgi.parse_multipart function is not implemented in this compatibility layer. "
        "CherryPy should not be calling this function directly."
    )

def escape(s, quote=None):
    """Mock function to satisfy imports but not meant to be used"""
    raise NotImplementedError(
        "The cgi.escape function is not implemented in this compatibility layer. "
        "CherryPy should not be calling this function directly."
    )