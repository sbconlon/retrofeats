# This file defines the logging object for the processor.

import os
from pathlib import Path

class Logger:
    def __init__(self, filename):
        # Remove old log file if it exists
        if os.path.exists(filename):
            os.remove(filename)
        # Make directories and file if it doesn't exit
        self.path = Path(filename)
        self.path.parent.mkdir(exist_ok=True, parents=True)

    def log(self, message=''):
        stream = self.path.open('a')
        stream.write(str(message) + '\n')
        stream.close()
