"""
Compatibility module to provide cgi.parse_header functionality
for Python 3.13+ where the cgi module has been removed.
"""

def parse_header(line):
    """
    Parse a Content-type like header.
    
    Return the main content-type and a dictionary of parameters.
    
    This replaces the deprecated cgi.parse_header function.
    """
    parts = line.split(';')
    main_value = parts[0].strip()
    params = {}
    
    for part in parts[1:]:
        if '=' not in part:
            continue
        key, value = part.split('=', 1)
        key = key.strip()
        
        # Handle quoted values
        value = value.strip()
        if value and value[0] == value[-1] == '"':
            value = value[1:-1]
            
        params[key] = value
    
    return main_value, params