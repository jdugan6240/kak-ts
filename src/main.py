import argparse
from kakoune import KakConnection
import logging
import os
import server
import sys


class StreamToLogger:
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """

    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ""

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())

    def flush(self):
        pass


parser = argparse.ArgumentParser(description="Tree Sitter server for Kakoune")
parser.add_argument(
    "-s",
    "--session",
    required=True,
    help="Kakoune session to communicate with",
)
parser.add_argument("-l", "--log", type=str, help="Write log to file")
parser.add_argument(
    "-v", "--verbosity", help="increase logging verbosity", action="count"
)
parser.add_argument("-b", "--buffer", type=str, required=True, help="Buffer to begin with")
parser.add_argument("-f", "--filetype", type=str, required=True, help="Filetype to begin with")

args = parser.parse_args()
session = args.session
buf = args.buffer
ft = args.filetype

# Determine log level
verbosity = 2
if args.verbosity:
    verbosity = args.verbosity
log_level = logging.CRITICAL
if verbosity == 2:
    log_level = logging.ERROR
elif verbosity == 3:
    log_level = logging.WARNING
elif verbosity == 4:
    log_level = logging.INFO
elif verbosity == 5:
    log_level = logging.DEBUG

# If the log flag is set, write log to a file
if args.log:
    logfile = args.log

    # If the file exists, delete it.
    # We don't want many sessions worth of logs.
    if os.path.exists(logfile):
        os.remove(logfile)

    logging.basicConfig(
        format="%(levelname)s@%(filename)s:%(lineno)d - %(message)s",
        filename=logfile,
        level=log_level,
        filemode="w",
    )

# Otherwise, log to the terminal
else:
    logging.basicConfig(
        format="%(levelname)s@%(filename)s:%(lineno)d - %(message)s",
        level=log_level,
    )


# Setup stderr to redirect to log
stderr_log = logging.getLogger("stderr")
sys.stderr = StreamToLogger(stderr_log, logging.ERROR)

logging.info(f"Starting kak-tree-sitter server for session {session}")

server.start(session, buf, ft)
