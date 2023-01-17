import sys
import logging

logger = logging.getLogger('Pol2Dom')

# Custom formatter for the console logger handler.
# Adapted from https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output
class Pol2DomLoggingFormatter(logging.Formatter):
    INDENT = 0

    bold_gray = '\033[1;90m'
    bold_green = '\033[1;92m'
    bold_yellow = '\033[1;33m'
    bold_red = '\033[1;91m'
    yellow = '\033[0;33m'
    red = '\033[0;91m'
    reset = '\033[0m'

    COLORS = {
        logging.DEBUG: (bold_gray, reset),
        logging.INFO: (bold_green, reset),
        logging.WARNING: (bold_yellow, yellow),
        logging.ERROR: (bold_red, red)
    }

    def format(self, record):
        level_color, message_color = self.COLORS.get(record.levelno)
        padding = ' ' * (10 - len(record.levelname))
        log_fmt = '  ' * self.INDENT + level_color + '{levelname}' + padding + message_color + '{message}' + self.reset
        formatter = logging.Formatter(log_fmt, style='{')
        return formatter.format(record)

def configure_logging(verbosity):
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(Pol2DomLoggingFormatter())

    logging.basicConfig(
        format='{levelname}\t{message}',
        style='{',
        level=eval('logging.' + verbosity.upper()),
        handlers=[console_handler]
    )

    requests_log = logging.getLogger('requests.packages.urllib3')
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True

    logger.setLevel(eval('logging.' + verbosity.upper()))
    logger.addHandler(console_handler)
    logger.propagate = False

