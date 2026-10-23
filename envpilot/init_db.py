from envpilot.db import Base, engine
from envpilot import models  # noqa: F401


if __name__ == "__main__":
    Base.metadata.create_all(engine)
