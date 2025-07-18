import pandas as pd

def load_catalog_excel(filepath):
    df = pd.read_excel(filepath)
    return df
