# This file defines the logging object for the processor.

from pathlib import Path

class Logger:
    def __init__(self, filename):
        self.path = Path(filename)
        self.path.parent.mkdir(exist_ok=True, parents=True)

    def log(self, message=''):
        stream = self.path.open('a')
        stream.write(str(message) + '\n')
        stream.close()
