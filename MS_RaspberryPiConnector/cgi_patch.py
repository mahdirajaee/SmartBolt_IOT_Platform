import sys
import email.parser

# Create a module-like object
class CGIModule:
    @staticmethod
    def parse_header(line):
        """Replacement for cgi.parse_header using email.parser"""
        if not line:
            return '', {}
        
        # Use email.parser for header parsing
        h = email.parser.HeaderParser()
        hdr = h.parsestr(f'Content-Type: {line}\n')
        return hdr.get_content_type(), dict(hdr.get_params(header='content-type'))

# Add the fake cgi module to sys.modules
sys.modules['cgi'] = CGIModule