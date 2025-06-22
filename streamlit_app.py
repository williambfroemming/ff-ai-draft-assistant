import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from src.player_pool_gsheet import load_player_pool_from_gsheet
from src.draft_board import load_draft_board_from_gsheet
from src.team_tracker import (
    get_my_team, get_available_players, assess_positional_gaps,
    prioritize_positions, suggest_nominations, summarize_opponents
)
from src.sync_player_pool import sync_player_pool_with_draft
from src.chat_assistant import ask_ai_assistant

# Config
PLAYER_POOL_SHEET_URL = "https://docs.google.com/spreadsheets/d/1e-pApi8FlsY_uU6IssQRP5_lrNRodhElba_g3R_8ntg/edit#gid=0"
DRAFT_BOARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1sMIZd7uLBC2vTwU_rnn4e3pTNGeOW1A0ROB62hP1EhQ/edit#gid=2026286613"
MY_NAME = "Bill"
TARGET_BUILD = {"QB": 2, "RB": 4, "WR": 5, "TE": 2, "DEF": 1}
POSITION_WEIGHTS = {"QB": 1.0, "RB": 0.9, "WR": 0.8, "TE": 0.6, "DEF": 0.2}

# Auto refresh every 30 seconds
# st_autorefresh(interval=30000, key="data_refresh")  # disabled for manual refresh control

# Title
st.title("🏈 Live Fantasy Draft AI Assistant")

# Sync and Load Data
@st.cache_data(ttl=30)
def get_cached_draft_board():
    return load_draft_board_from_gsheet(DRAFT_BOARD_SHEET_URL, "Draft")

draft_board = get_cached_draft_board()
# Optional manual sync via button
if st.sidebar.button("🔄 Sync Player Pool with Draft Board"):
    sync_player_pool_with_draft(PLAYER_POOL_SHEET_URL, draft_board)
    st.sidebar.success("Player pool synced!")
@st.cache_data(ttl=30)
def get_cached_player_pool():
    return load_player_pool_from_gsheet(PLAYER_POOL_SHEET_URL, worksheet_name="PlayerPool")

player_pool = get_cached_player_pool()

# Process Data
available_players = get_available_players(player_pool, draft_board)
my_team = get_my_team(draft_board, manager_name=MY_NAME)
priority_gaps = prioritize_positions(my_team["position_counts"], TARGET_BUILD, POSITION_WEIGHTS)
opponent_summary = summarize_opponents(draft_board, MY_NAME)

# GPT Draft Insight Filtering
st.sidebar.header("🧠 GPT Insight Filters")
selected_position = st.sidebar.selectbox("Filter by Position:", ["All"] + sorted([pos for pos in draft_board["Position"].dropna().unique() if str(pos).strip() != ""]))
selected_manager = st.sidebar.selectbox("Filter by Manager:", ["All"] + sorted([mgr for mgr in draft_board["Drafted By"].dropna().unique() if str(mgr).strip() != ""]))

filtered_draft = draft_board.copy()
if selected_position != "All":
    filtered_draft = filtered_draft[filtered_draft["Position"] == selected_position]
if selected_manager != "All":
    filtered_draft = filtered_draft[filtered_draft["Drafted By"] == selected_manager]

# Generate Opponent Draft Summary for GPT
def summarize_opponents_rosters(draft_df: pd.DataFrame, my_name: str) -> str:
    grouped = draft_df.groupby("Drafted By")
    summaries = []
    for manager, picks in grouped:
        if manager.strip().lower() == my_name.strip().lower():
            continue
        summary = picks[["Player", "Position", "Price"]].to_string(index=False)
        summaries.append(f"{manager} drafted:\n{summary}")
    return "\n\n".join(summaries)

opponent_rosters = summarize_opponents_rosters(filtered_draft, MY_NAME)
last_picks = filtered_draft.tail(5).copy()

# Inject summary into prompt


# Layout
st.header("💰 My Team Status")
st.metric("Remaining Budget", f"${my_team['remaining_budget']:.2f}")
st.metric("Players Drafted", my_team['roster'].shape[0])
st.metric("Available Players", available_players.shape[0])

st.subheader("📖 All Remaining Players")
st.dataframe(available_players[['Player', 'Position', 'Team']])

st.subheader("📋 My Current Team")
st.dataframe(my_team['roster'][['Player', 'Position', 'Price']])

st.subheader("📌 Suggested Positional Gaps")
for pos, gap in assess_positional_gaps(my_team["position_counts"], TARGET_BUILD).items():
    if gap > 0:
        st.write(f"- Need {gap} more {pos}(s)")

st.subheader("📈 Prioritized Positional Needs")
for pos, score in priority_gaps.items():
    if score > 0:
        st.write(f"- {pos}: priority score {score:.2f}")

col1, col2 = st.columns(2)

with col1:
    st.header("🎯 Nomination Strategies")
    st.subheader("💸 Budget Drainers")
    st.dataframe(suggest_nominations(available_players, my_team["position_counts"], TARGET_BUILD, priority_gaps, strategy="drain")[["Player", "Position"]])

    st.subheader("👻 Decoys")
    st.dataframe(suggest_nominations(available_players, my_team["position_counts"], TARGET_BUILD, priority_gaps, strategy="decoy")[["Player", "Position"]])

    st.subheader("🔒 Stealth Targets")
    st.dataframe(suggest_nominations(available_players, my_team["position_counts"], TARGET_BUILD, priority_gaps, strategy="target")[["Player", "Position"]])

with col2:
    st.header("🧍‍♂️ Opponent Summary")
    st.dataframe(opponent_summary)

st.header("🧑‍🤝‍🧑 Opponent Teams")
selected_team = st.selectbox("View Drafted Players by Manager:", sorted([mgr for mgr in draft_board["Drafted By"].dropna().unique() if str(mgr).strip() != ""]))
filtered_team = draft_board[draft_board["Drafted By"] == selected_team][["Player", "Position", "Price"]]
st.dataframe(filtered_team)

if st.button("💡 Refresh Dashboard with GPT Summary"):
    sync_player_pool_with_draft(PLAYER_POOL_SHEET_URL, draft_board)
    st.success("Player pool synced!")

    opponent_rosters = summarize_opponents_rosters(filtered_draft, MY_NAME)
    last_picks = filtered_draft.tail(5).copy()

    gpt_prompt = f"""
    Here is a summary of the last 5 draft picks:
    {last_picks[['Player', 'Drafted By', 'Price']].to_string(index=False)}

    Here is a summary of all opponent rosters:
    {opponent_rosters}

    What strategic trends or moves are emerging in these recent picks?
    """
    ai_summary = ask_ai_assistant(gpt_prompt, my_team, draft_board, available_players, MY_NAME)
    st.markdown(f"**AI Summary:**{ai_summary}")

user_question = st.text_input("🤖 Ask GPT a draft question:")
if user_question:
    answer = ask_ai_assistant(user_question, my_team, draft_board, available_players, MY_NAME)
    st.markdown(f"**AI Assistant:** {answer}")
