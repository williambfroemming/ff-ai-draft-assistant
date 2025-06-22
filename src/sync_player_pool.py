import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def sync_player_pool_with_draft(player_sheet_url, draft_df):
    # Connect to Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("secrets/service_account.json", scope)
    client = gspread.authorize(creds)

    # Load player pool sheet
    player_sheet = client.open_by_url(player_sheet_url)
    worksheet = player_sheet.worksheet("PlayerPool")
    player_data = worksheet.get_all_records()
    player_df = pd.DataFrame(player_data)

    # Normalize for matching
    player_df["Player_lower"] = player_df["Player"].str.strip().str.lower()
    draft_df["Player_lower"] = draft_df["Player"].str.strip().str.lower()

    # Merge draft info
    merged = player_df.merge(
        draft_df[["Player_lower", "Price", "Drafted By"]],
        on="Player_lower",
        how="left"
    )

    # Update synced fields
    merged["Removed"] = merged["Price"].notnull()
    merged["PricePaid"] = merged["Price"]
    merged["TeamDraftedBy"] = merged["Drafted By"]

    # Drop helper columns
    merged = merged.drop(columns=["Player_lower", "Price", "Drafted By"])

    # Convert NaNs to blank strings to avoid JSON serialization errors
    merged = merged.fillna("")

    # Push updates back to sheet
    worksheet.update([merged.columns.values.tolist()] + merged.values.tolist())
