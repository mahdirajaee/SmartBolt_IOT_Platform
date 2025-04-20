"""
Patch module for CherryPy to work with Python 3.13+
where the cgi module has been removed.
"""
import sys
from importlib import import_module

def patch_cherrypy():
    """
    Apply patches to make CherryPy work with Python 3.13+
    """
    # Check if we're running Python 3.13+
    if sys.version_info >= (3, 13):
        # Create a mock cgi module with the required functions
        import types
        
        # Import our compatibility functions
        from cgi_compat import parse_header
        
        # Create a mock cgi module
        mock_cgi = types.ModuleType('cgi')
        mock_cgi.parse_header = parse_header
        
        # Add it to sys.modules
        sys.modules['cgi'] = mock_cgi
        
        print("Applied compatibility patch for CherryPy on Python 3.13+")