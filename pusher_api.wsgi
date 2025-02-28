import sys
import os

# Add the directory containing your app to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# Import your app as 'application'
from pusher_api import app as application
