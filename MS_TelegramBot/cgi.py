"""
This is a minimal replacement for the deprecated cgi module that CherryPy depends on.
Only implements the parse_header function which is needed by CherryPy.
"""

def parse_header(line):
    """Parse a Content-type like header.
    
    Return the main content-type and a dictionary of parameters.
    """
    parts = line.split(';')
    key = parts[0].strip()
    params = {}
    
    for param in parts[1:]:
        if '=' not in param:
            continue
        name, value = param.split('=', 1)
        name = name.strip()
        value = value.strip()
        
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
            
        params[name] = value
        
    return key, params