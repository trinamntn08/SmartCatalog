import pandas as pd

def load_known_brands(csv_path="config/brands/known_brands.csv"):
    try:
        df = pd.read_csv(csv_path)
        brand_list = df["brand"].dropna().astype(str).tolist()
        return brand_list
    except Exception as e:
        print(f"[ERROR] Không thể tải known_brands.csv: {e}")
        return []
