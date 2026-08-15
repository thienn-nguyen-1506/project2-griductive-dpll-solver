from gui.app import run_app
from gui.real_gateway import RealGameGateway


if __name__ == "__main__":
    run_app(gateway=RealGameGateway())
