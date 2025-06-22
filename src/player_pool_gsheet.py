import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

def load_player_pool_from_gsheet(sheet_url: str, worksheet_name: str = "PlayerPool") -> pd.DataFrame:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("secrets/service_account.json", scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_url(sheet_url)
    worksheet = sheet.worksheet(worksheet_name)
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    # Clean/standardize column names
    df.columns = df.columns.str.strip().str.replace(" ", "_")

    # Normalize position (e.g., WR1 → WR)
    df["Position"] = df["Position"].str.extract(r"([A-Z]+)")

    return df
