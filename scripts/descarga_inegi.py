# src/scripts/mapea.py
import sys

from src.configuraciones.config_params import conf, logger
from src.datos.get_inegi import GetInegi


def main():

    
    obj = GetInegi(False)
    obj.run()


if __name__ == "__main__":
    main()