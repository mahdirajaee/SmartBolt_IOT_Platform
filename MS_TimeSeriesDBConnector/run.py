import os
from dotenv import load_dotenv
import sys

# Load environment variables from .env file
load_dotenv()

# Make sure we can run the service without Resource Catalog
if len(sys.argv) > 1 and sys.argv[1] == '--no-catalog':
    os.environ['CATALOG_ENABLED'] = 'false'
else:
    os.environ['CATALOG_ENABLED'] = 'true'

# Start the TimeSeriesDBConnector
from TimeSeriesDBConnector import main
main()