#!/usr/bin/python3

# Initialize Cassandra so that the charm can run that once at installation step
# before multiple process run in parallel and step on each others toes.

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


from errortracker import cassandra, config  # noqa: E402

logger = config.logger
# Make sure to output logs to stdout
logger.addHandler(logging.StreamHandler(sys.stdout))

cassandra.setup_cassandra()
