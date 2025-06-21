import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

def load_draft_board_from_gsheet(sheet_url: str, worksheet_name: str) -> pd.DataFrame:
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("secrets/service_account.json", scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_url(sheet_url)
    worksheet = sheet.worksheet(worksheet_name)
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

df_draft = load_draft_board_from_gsheet(
    sheet_url="https://docs.google.com/spreadsheets/d/1sMIZd7uLBC2vTwU_rnn4e3pTNGeOW1A0ROB62hP1EhQ/edit?gid=2026286613#gid=2026286613",
    worksheet_name="Draft"
)