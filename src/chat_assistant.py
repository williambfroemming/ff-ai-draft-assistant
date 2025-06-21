import os
import openai
import pandas as pd

# Required for openai>=1.0.0
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def summarize_opponents_rosters(draft_board: pd.DataFrame, my_name: str) -> str:
    summaries = []
    grouped = draft_board.groupby("Drafted By")

    for manager, picks in grouped:
        if manager.strip().lower() == my_name.strip().lower():
            continue
        summary = picks[["Player", "Position", "Price"]].to_string(index=False)
        summaries.append(f"{manager}:\n{summary}")

    return "\n\n".join(summaries)

def ask_ai_assistant(prompt: str,
                     my_team: dict,
                     draft_board: pd.DataFrame,
                     available_players: pd.DataFrame,
                     my_name: str = "Bill") -> str:
    team_roster = my_team["roster"][["Player", "Position", "Price"]].to_string(index=False)
    budget = my_team["remaining_budget"]
    needs = my_team["position_counts"]
    available = available_players.head(10)[["Player", "Position"]].to_string(index=False)
    opponent_rosters = summarize_opponents_rosters(draft_board, my_name)

    context = f"""
You are a fantasy football auction draft assistant.

User's current team:
{team_roster}

Remaining budget: ${budget}
Current position counts: {needs}

Top available players:
{available}

Opponent draft summaries:
{opponent_rosters}

There have been {len(draft_board)} picks in the draft so far.

Answer the user's question based on this context.
"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": context},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    return response.choices[0].message.content

