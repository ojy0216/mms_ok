import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.basicConfig(
    format="%(asctime)s | %(prefix)s | %(levelname)s >> %(message)s",
)

from .logger import log
from .pipeoutdata import PipeOutData
