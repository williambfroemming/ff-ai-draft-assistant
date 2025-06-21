import pandas as pd
import random


def get_my_team(draft_board: pd.DataFrame, manager_name: str, budget: float = 200.0):
    my_picks = draft_board[draft_board["Drafted By"].str.lower() == manager_name.lower()]
    total_spent = my_picks["Price"].sum()
    remaining_budget = budget - total_spent
    position_counts = my_picks["Position"].value_counts().to_dict()
    return {
        "roster": my_picks,
        "spent": total_spent,
        "remaining_budget": remaining_budget,
        "position_counts": position_counts
    }

def get_available_players(player_pool: pd.DataFrame, draft_board: pd.DataFrame) -> pd.DataFrame:
    drafted_players = draft_board['Player'].str.strip().str.lower().tolist()
    available = player_pool[~player_pool['Player'].str.strip().str.lower().isin(drafted_players)]
    return available

def assess_positional_gaps(position_counts: dict, target_build: dict) -> dict:
    gaps = {}
    for pos, target in target_build.items():
        drafted = position_counts.get(pos, 0)
        gaps[pos] = target - drafted
    return gaps

def prioritize_positions(position_counts: dict, target_build: dict, position_weights: dict) -> dict:
    gaps = {}
    for pos, target in target_build.items():
        drafted = position_counts.get(pos, 0)
        need = max(0, target - drafted)
        weight = position_weights.get(pos, 0.5)  # default weight if missing
        gaps[pos] = need * weight
    sorted_gaps = dict(sorted(gaps.items(), key=lambda item: item[1], reverse=True))
    return sorted_gaps

def recommend_players(available_pool: pd.DataFrame,
                      prioritized_positions: dict,
                      budget_remaining: float,
                      max_recommendations: int = 10) -> pd.DataFrame:
    # Filter only top-priority positions
    top_positions = [pos for pos, score in prioritized_positions.items() if score > 0]

    filtered = available_pool[available_pool['Position'].isin(top_positions)].copy()

    # If you have an auction value column later, you can filter by it here too
    # e.g., filtered = filtered[filtered['AuctionValue'] <= budget_remaining]

    # For now: return top N players by appearance in list (could sort by ECR if available)
    return filtered.head(max_recommendations)

def suggest_nominations(available_pool: pd.DataFrame,
                         my_position_counts: dict,
                         target_build: dict,
                         priority_positions: dict,
                         strategy: str = "drain",
                         max_suggestions: int = 3) -> pd.DataFrame:
    if strategy == "drain":
        positions_filled = [pos for pos in target_build if my_position_counts.get(pos, 0) >= target_build[pos]]
        pool = available_pool[available_pool["Position"].isin(positions_filled)]
        if pool.empty:
            pool = available_pool  # fallback
        return pool.head(max_suggestions)

    elif strategy == "decoy":
        # Decoy players must be somewhat valuable (e.g., early top 100 picks)
        decoy_positions = [pos for pos, score in priority_positions.items() if score < 0.5]
        pool = available_pool[available_pool["Position"].isin(decoy_positions)].copy()

        # Limit to top-ranked (simulate “likely to be drafted soon”)
        pool = pool.head(100)  # assumes player pool is sorted by ECR or importance

        # If not enough, fallback to something viable
        if pool.empty:
            pool = available_pool.head(100)

        return pool.sample(n=min(max_suggestions, len(pool)))


    elif strategy == "target":
        top_positions = [pos for pos, score in priority_positions.items() if score > 0]
        pool = available_pool[available_pool["Position"].isin(top_positions)]
        if pool.empty:
            pool = available_pool  # fallback
        return pool.head(max_suggestions)

    else:
        return pd.DataFrame()  # fallback


def summarize_opponents(draft_board: pd.DataFrame,
                        my_name: str,
                        starting_budget: float = 200.0) -> pd.DataFrame:
    grouped = draft_board.groupby("Drafted By")

    draft_board["Price"] = pd.to_numeric(draft_board["Price"], errors="coerce")

    summaries = []
    for manager, group in grouped:
        if manager.strip().lower() == my_name.strip().lower():
            continue  # skip yourself

        total_spent = group["Price"].sum()
        remaining_budget = starting_budget - total_spent
        num_players = group.shape[0]

        summaries.append({
            "Manager": manager,
            "Spent": total_spent,
            "Remaining": remaining_budget,
            "Players Drafted": num_players
        })

    return pd.DataFrame(summaries).sort_values(by="Remaining", ascending=False)
