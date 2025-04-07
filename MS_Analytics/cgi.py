"""
This is a compatibility module to provide the functionality of the deprecated cgi module
which was removed in Python 3.13. This specifically implements the parse_header function
that CherryPy depends on.
"""

from email.parser import HeaderParser
from email.message import Message

def parse_header(line):
    """Parse a Content-type like header.
    
    Return the main content-type and a dictionary of parameters.
    """
    if not line:
        return '', {}
        
    # Create a Message object and use the HeaderParser to parse it
    h = HeaderParser().parsestr(f'Content-Type: {line}')
    
    # Get the content type
    main_value = h.get_content_type()
    
    # Get the parameters
    params = {}
    for key, value in h.get_params()[1:]:  # Skip the first one as it's the main value
        params[key] = value
        
    return main_value, params

def parse_multipart(fp, pdict):
    """Parse multipart input.
    
    This is a stub to prevent import errors. It's not actually needed for CherryPy's usage.
    """
    raise NotImplementedError("parse_multipart is not implemented in this compatibility module")

def parse_qs(qs, keep_blank_values=0, strict_parsing=0, encoding='utf-8', errors='replace'):
    """Parse a query given as a string argument.
    
    This is a stub to prevent import errors. It's not actually needed for CherryPy's usage.
    """
    raise NotImplementedError("parse_qs is not implemented in this compatibility module")

def escape(s, quote=None):
    """Replace special characters '&', '<' and '>' by HTML-safe sequences.
    
    This is a stub to prevent import errors. It's not actually needed for CherryPy's usage.
    """
    raise NotImplementedError("escape is not implemented in this compatibility module")