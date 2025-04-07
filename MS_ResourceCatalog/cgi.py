def parse_header(header):
    """
    Parse a Content-type header.
    
    Args:
        header (str): The header string to parse.
    
    Returns:
        tuple: A tuple of (main_value, params)
    """
    if not header:
        return '', {}
    
    parts = header.split(';')
    main_value = parts[0].strip()
    
    # Parse parameters
    params = {}
    for param in parts[1:]:
        if '=' in param:
            key, value = param.split('=', 1)
            params[key.strip()] = value.strip().strip('"')
    
    return main_value, params