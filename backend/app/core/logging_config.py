import logging
import sys

def setup_logging():
    """
    Configures the root logger for the application.
    Returns a configured logger instance.
    """
    logger = logging.getLogger("DAA")
    logger.setLevel(logging.INFO)
    
    # Prevent adding multiple handlers if function is called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        # Add File Handler
        import os
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
        os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(os.path.join(log_dir, "daa.log"))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

# Create a global logger instance
logger = setup_logging()
