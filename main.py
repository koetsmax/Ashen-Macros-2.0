from core.logging import setup_logging
from gui.app import App

if __name__ == "__main__":
    setup_logging()
    App().run()
