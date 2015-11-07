"""
Configuration of 'gcal' Flask app.
Edit to fit development or deployment environment.

"""
import random

# localhost
PORT = 5000
DEBUG = True

# ix.cs.uoregon.edu
# PORT = random.randint(5000, 8000)
# DEBUG = False  # Because it's unsafe to run outside localhost

# both
GOOGLE_LICENSE_KEY = ''
MONGO_PW = ''
MONGO_USER = ''
MONGO_PORT = 0
MONGO_URL = 'mongodb://{$MONGO_USER}:{$MONGO_PW}@localhost:{$MONGO_PORT}/gcal'
