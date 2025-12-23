
from src.configuraciones.config_params import conf, logger
from src.datos.EDA import EDA


if __name__ == "__main__":

    raw_file = conf["data"]["raw_data_file"]
        
    carga_dataset = EDA(raw_file)

    carga_dataset.run()