import sys
import email.parser

class CGIModule:
    @staticmethod
    def parse_header(line):
        """Replacement for cgi.parse_header using email.parser"""
        if not line:
            return '', {}
        
        h = email.parser.HeaderParser()
        hdr = h.parsestr(f'Content-Type: {line}\n')
        return hdr.get_content_type(), dict(hdr.get_params(header='content-type'))

sys.modules['cgi'] = CGIModule 