import pandas as pd
from src.player_pool import load_player_pool
from src.draft_board import load_draft_board_from_gsheet
from src.team_tracker import get_available_players, get_my_team, assess_positional_gaps, prioritize_positions
from src.team_tracker import (
    get_my_team, get_available_players, assess_positional_gaps,
    prioritize_positions, recommend_players, suggest_nominations,
    summarize_opponents
)

TARGET_BUILD = {
    "QB": 2,     # for Superflex
    "RB": 4,     # 2 starters + 2 depth
    "WR": 5,     # 3 starters + 2 depth
    "TE": 2,     # 1 starter + backup
    "DEF": 1
}

POSITION_WEIGHTS = {
    "QB": 1.0,
    "RB": 0.9,
    "WR": 0.8,
    "TE": 0.6,
    "DEF": 0.2
}

# Load data
player_pool = load_player_pool("data/FantasyPros_2025_Draft_ALL_Rankings.csv")
draft_board = load_draft_board_from_gsheet("https://docs.google.com/spreadsheets/d/1sMIZd7uLBC2vTwU_rnn4e3pTNGeOW1A0ROB62hP1EhQ/edit?gid=2026286613#gid=2026286613", "Draft")

# Process
available_players = get_available_players(player_pool, draft_board)
my_team = get_my_team(draft_board, manager_name="Bill")

print("Remaining budget:", my_team["remaining_budget"])
print("Remaining players:", available_players.shape[0])

gaps = assess_positional_gaps(my_team["position_counts"], TARGET_BUILD)

print("Suggested positional targets:")
for pos, gap in gaps.items():
    if gap > 0:
        print(f"  Add {gap} more {pos}(s)")

priority_gaps = prioritize_positions(my_team["position_counts"], TARGET_BUILD, POSITION_WEIGHTS)

print("Prioritized positional needs:")
for pos, score in priority_gaps.items():
    if score > 0:
        print(f"  {pos}: priority score {score}")

recommended = recommend_players(
    available_pool=available_players,
    prioritized_positions=priority_gaps,
    budget_remaining=my_team["remaining_budget"]
)

print("🧠 Recommended Players to Target:")
print(recommended[['Player', 'Position', 'Team']])

print("\n💸 Budget Drainer Nominations:")
print(suggest_nominations(available_players, my_team["position_counts"], TARGET_BUILD, priority_gaps, strategy="drain")[["Player", "Position"]])

print("\n👻 Decoy Nominations:")
print(suggest_nominations(available_players, my_team["position_counts"], TARGET_BUILD, priority_gaps, strategy="decoy")[["Player", "Position"]])

print("\n🎯 Stealth Target Nominations:")
print(suggest_nominations(available_players, my_team["position_counts"], TARGET_BUILD, priority_gaps, strategy="target")[["Player", "Position"]])

opponent_summary = summarize_opponents(draft_board, my_name="Bill")

print("\n💰 Opponent Budgets:")
print(opponent_summary)


from src.chat_assistant import ask_ai_assistant

while True:
    question = input("\n🤖 Ask your AI Assistant: ")
    if question.lower() in ["exit", "quit"]:
        break

    response = ask_ai_assistant(
        prompt=question,
        my_team=my_team,
        draft_board=draft_board,
        available_players=available_players,
        my_name="Bill"  # or whoever you are in the draft board
    )

    print("\nAI Draft Assistant:\n", response)
