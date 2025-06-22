import streamlit as st
import pandas as pd
import time
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from src.player_pool_gsheet import load_player_pool_from_gsheet
from src.draft_board import load_draft_board_from_gsheet
from src.team_tracker import (
    get_my_team, get_available_players, assess_positional_gaps,
    prioritize_positions, suggest_nominations, summarize_opponents
)
from src.sync_player_pool import sync_player_pool_with_draft
from src.chat_assistant import ask_ai_assistant

# Page config
st.set_page_config(
    page_title="Fantasy Draft AI Assistant",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #ff6b35;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 0.75rem 1.25rem;
        margin-bottom: 1rem;
        border-radius: 0.25rem;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        color: #856404;
        padding: 0.75rem 1.25rem;
        margin-bottom: 1rem;
        border-radius: 0.25rem;
    }
    .stAlert > div {
        padding-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Config
PLAYER_POOL_SHEET_URL = "https://docs.google.com/spreadsheets/d/1e-pApi8FlsY_uU6IssQRP5_lrNRodhElba_g3R_8ntg/edit#gid=0"
DRAFT_BOARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1sMIZd7uLBC2vTwU_rnn4e3pTNGeOW1A0ROB62hP1EhQ/edit#gid=2026286613"
DEFAULT_BUDGET = 200.0

# Session state initialization
if 'my_name' not in st.session_state:
    st.session_state.my_name = "Bill"
if 'target_build' not in st.session_state:
    st.session_state.target_build = {"QB": 2, "RB": 4, "WR": 5, "TE": 2, "DEF": 1}
if 'position_weights' not in st.session_state:
    st.session_state.position_weights = {"QB": 1.0, "RB": 0.9, "WR": 0.8, "TE": 0.6, "DEF": 0.2}
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# Sidebar Configuration
st.sidebar.header("⚙️ Configuration")

# Manager name input
st.session_state.my_name = st.sidebar.text_input("Your Manager Name:", value=st.session_state.my_name)

# Auto-refresh toggle
st.session_state.auto_refresh = st.sidebar.checkbox("Auto-refresh (30s)", value=st.session_state.auto_refresh)

if st.session_state.auto_refresh:
    st_autorefresh(interval=30000, key="data_refresh")

# Target roster configuration
st.sidebar.subheader("🎯 Target Roster")
for pos in st.session_state.target_build.keys():
    st.session_state.target_build[pos] = st.sidebar.number_input(
        f"{pos}:", 
        min_value=0, 
        max_value=10, 
        value=st.session_state.target_build[pos],
        key=f"target_{pos}"
    )

# Position weights configuration
st.sidebar.subheader("⚖️ Position Weights")
for pos in st.session_state.position_weights.keys():
    st.session_state.position_weights[pos] = st.sidebar.slider(
        f"{pos} Weight:", 
        min_value=0.0, 
        max_value=2.0, 
        value=st.session_state.position_weights[pos],
        step=0.1,
        key=f"weight_{pos}"
    )

# Title
st.title("🏈 Live Fantasy Draft AI Assistant")
st.markdown(f"**Manager:** {st.session_state.my_name} | **Last Updated:** {datetime.now().strftime('%H:%M:%S')}")

# Error handling wrapper
def safe_load_data():
    try:
        with st.spinner("Loading draft data..."):
            draft_board = load_draft_board_from_gsheet(DRAFT_BOARD_SHEET_URL, "Draft")
            if draft_board.empty:
                st.warning("Draft board is empty or could not be loaded.")
                return None, None
                
        with st.spinner("Loading player pool..."):
            player_pool = load_player_pool_from_gsheet(PLAYER_POOL_SHEET_URL, worksheet_name="PlayerPool")
            if player_pool.empty:
                st.warning("Player pool is empty or could not be loaded.")
                return draft_board, None
                
        return draft_board, player_pool
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None, None

# Load data with error handling
draft_board, player_pool = safe_load_data()

if draft_board is None or player_pool is None:
    st.stop()

# Data validation
required_draft_columns = ['Player', 'Position', 'Price', 'Drafted By']
missing_draft_cols = [col for col in required_draft_columns if col not in draft_board.columns]
if missing_draft_cols:
    st.error(f"Draft board missing required columns: {missing_draft_cols}")
    st.stop()

required_player_columns = ['Player', 'Position']
missing_player_cols = [col for col in required_player_columns if col not in player_pool.columns]
if missing_player_cols:
    st.error(f"Player pool missing required columns: {missing_player_cols}")
    st.stop()

# Manual sync button
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("🔄 Sync Data", help="Sync player pool with current draft board"):
        try:
            with st.spinner("Syncing data..."):
                sync_player_pool_with_draft(PLAYER_POOL_SHEET_URL, draft_board)
                time.sleep(1)  # Brief pause for sync
                st.rerun()
        except Exception as e:
            st.error(f"Sync failed: {str(e)}")

# Process Data
try:
    available_players = get_available_players(player_pool, draft_board)
    my_team = get_my_team(draft_board, manager_name=st.session_state.my_name, budget=DEFAULT_BUDGET)
    priority_gaps = prioritize_positions(my_team["position_counts"], st.session_state.target_build, st.session_state.position_weights)
    opponent_summary = summarize_opponents(draft_board, st.session_state.my_name, starting_budget=DEFAULT_BUDGET)
except Exception as e:
    st.error(f"Error processing data: {str(e)}")
    st.stop()

# Key Metrics Dashboard
st.header("📊 Dashboard Overview")
col1, col2, col3, col4 = st.columns(4)

with col1:
    budget_color = "normal" if my_team['remaining_budget'] > 50 else "inverse"
    st.metric("💰 Remaining Budget", f"${my_team['remaining_budget']:.2f}", delta=None)

with col2:
    st.metric("👥 Players Drafted", f"{my_team['roster'].shape[0]}", delta=None)

with col3:
    total_target = sum(st.session_state.target_build.values())
    roster_completion = (my_team['roster'].shape[0] / total_target) * 100 if total_target > 0 else 0
    st.metric("📈 Roster Completion", f"{roster_completion:.1f}%", delta=None)

with col4:
    st.metric("🎯 Available Players", f"{available_players.shape[0]}", delta=None)

# Alerts and warnings
if my_team['remaining_budget'] < 10:
    st.error("⚠️ Low budget alert! Consider value picks.")
elif my_team['remaining_budget'] < 25:
    st.warning("💡 Budget getting tight. Focus on必需positions.")

# Critical position needs
critical_needs = [pos for pos, gap in assess_positional_gaps(my_team["position_counts"], st.session_state.target_build).items() if gap > 0]
if critical_needs:
    st.info(f"🎯 Critical needs: {', '.join(critical_needs)}")

# Main content tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏠 Overview", "👥 My Team", "🎯 Strategy", "🧍‍♂️ Opponents", "🤖 AI Assistant"])

with tab1:
    st.subheader("📋 Recent Draft Activity")
    if not draft_board.empty:
        recent_picks = draft_board.tail(10)[['Player', 'Position', 'Price', 'Drafted By']].sort_index(ascending=False)
        st.dataframe(recent_picks, use_container_width=True)
    
    st.subheader("🔥 Top Available Players by Position")
    if not available_players.empty:
        for pos in ['QB', 'RB', 'WR', 'TE', 'DEF']:
            pos_players = available_players[available_players['Position'] == pos].head(5)
            if not pos_players.empty:
                st.write(f"**{pos}:** {', '.join(pos_players['Player'].tolist())}")

with tab2:
    st.subheader("💼 Current Roster")
    if not my_team['roster'].empty:
        roster_display = my_team['roster'][['Player', 'Position', 'Price']].copy()
        roster_display['Price'] = roster_display['Price'].apply(lambda x: f"${x:.0f}")
        st.dataframe(roster_display, use_container_width=True)
    else:
        st.info("No players drafted yet.")
    
    st.subheader("📊 Position Breakdown")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Current vs Target:**")
        for pos, target in st.session_state.target_build.items():
            current = my_team["position_counts"].get(pos, 0)
            gap = target - current
            status = "✅" if gap <= 0 else "❌" if gap >= 2 else "⚠️"
            st.write(f"{status} {pos}: {current}/{target} (need {max(0, gap)})")
    
    with col2:
        st.write("**Spending by Position:**")
        if not my_team['roster'].empty:
            spending_by_pos = my_team['roster'].groupby('Position')['Price'].sum().sort_values(ascending=False)
            for pos, amount in spending_by_pos.items():
                st.write(f"💰 {pos}: ${amount:.0f}")

with tab3:
    st.subheader("🎯 Nomination Strategies")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("**💸 Budget Drainers**")
        drainers = suggest_nominations(available_players, my_team["position_counts"], 
                                     st.session_state.target_build, priority_gaps, strategy="drain")
        if not drainers.empty:
            st.dataframe(drainers[["Player", "Position"]].head(5), use_container_width=True)
        else:
            st.info("No budget drainers identified")
    
    with col2:
        st.write("**👻 Decoy Nominations**")
        decoys = suggest_nominations(available_players, my_team["position_counts"], 
                                   st.session_state.target_build, priority_gaps, strategy="decoy")
        if not decoys.empty:
            st.dataframe(decoys[["Player", "Position"]].head(5), use_container_width=True)
        else:
            st.info("No decoy players suggested")
    
    with col3:
        st.write("**🔒 Target Players**")
        targets = suggest_nominations(available_players, my_team["position_counts"], 
                                    st.session_state.target_build, priority_gaps, strategy="target")
        if not targets.empty:
            st.dataframe(targets[["Player", "Position"]].head(5), use_container_width=True)
        else:
            st.info("No target players identified")
    
    st.subheader("📈 Position Priority Scores")
    priority_df = pd.DataFrame(list(priority_gaps.items()), columns=['Position', 'Priority Score'])
    priority_df = priority_df[priority_df['Priority Score'] > 0].sort_values('Priority Score', ascending=False)
    if not priority_df.empty:
        st.dataframe(priority_df, use_container_width=True)
    else:
        st.success("🎉 All position needs met based on current targets!")

with tab4:
    st.subheader("🧍‍♂️ Opponent Analysis")
    if not opponent_summary.empty:
        st.dataframe(opponent_summary, use_container_width=True)
    
    st.subheader("👀 View Opponent Rosters")
    if not draft_board.empty:
        managers = sorted([mgr for mgr in draft_board["Drafted By"].dropna().unique() 
                          if str(mgr).strip() != "" and mgr.lower() != st.session_state.my_name.lower()])
        if managers:
            selected_manager = st.selectbox("Select Manager:", managers)
            manager_team = draft_board[draft_board["Drafted By"] == selected_manager][["Player", "Position", "Price"]]
            if not manager_team.empty:
                st.dataframe(manager_team, use_container_width=True)
                
                # Manager analysis
                manager_spending = manager_team['Price'].sum()
                manager_remaining = DEFAULT_BUDGET - manager_spending
                st.write(f"**{selected_manager}** - Spent: ${manager_spending:.0f} | Remaining: ${manager_remaining:.0f}")
            else:
                st.info(f"{selected_manager} hasn't drafted any players yet.")

with tab5:
    st.subheader("🤖 AI Draft Assistant")
    
    # Quick action buttons
    st.write("**Quick Insights:**")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Analyze Recent Picks"):
            if not draft_board.empty:
                recent_analysis_prompt = "Analyze the last 10 draft picks and identify any trends, values, or strategic moves I should be aware of."
                with st.spinner("Analyzing recent picks..."):
                    response = ask_ai_assistant(recent_analysis_prompt, my_team, draft_board, available_players, st.session_state.my_name)
                    st.session_state.chat_history.append(("System", recent_analysis_prompt, response))
                    st.write("**AI Analysis:**")
                    st.write(response)
    
    with col2:
        if st.button("🎯 Get Position Advice"):
            position_advice_prompt = "Based on my current roster and remaining budget, what positions should I prioritize and what's my optimal strategy moving forward?"
            with st.spinner("Getting position advice..."):
                response = ask_ai_assistant(position_advice_prompt, my_team, draft_board, available_players, st.session_state.my_name)
                st.session_state.chat_history.append(("System", position_advice_prompt, response))
                st.write("**AI Advice:**")
                st.write(response)
    
    with col3:
        if st.button("💰 Budget Strategy"):
            budget_prompt = f"I have ${my_team['remaining_budget']:.0f} remaining. What's the optimal way to spend this budget given my current needs?"
            with st.spinner("Analyzing budget strategy..."):
                response = ask_ai_assistant(budget_prompt, my_team, draft_board, available_players, st.session_state.my_name)
                st.session_state.chat_history.append(("System", budget_prompt, response))
                st.write("**Budget Strategy:**")
                st.write(response)
    
    # Custom question input
    st.write("**Ask Custom Question:**")
    user_question = st.text_input("Enter your draft question:", placeholder="e.g., Should I target RBs or WRs next?")
    
    if st.button("Ask AI") and user_question:
        with st.spinner("Getting AI response..."):
            try:
                response = ask_ai_assistant(user_question, my_team, draft_board, available_players, st.session_state.my_name)
                st.session_state.chat_history.append(("User", user_question, response))
                st.write("**AI Response:**")
                st.write(response)
            except Exception as e:
                st.error(f"Error getting AI response: {str(e)}")
    
    # Chat history
    if st.session_state.chat_history:
        st.subheader("💬 Recent AI Conversations")
        for i, (question_type, question, response) in enumerate(reversed(st.session_state.chat_history[-5:])):
            with st.expander(f"{question_type}: {question[:50]}..." if len(question) > 50 else f"{question_type}: {question}"):
                st.write(f"**Q:** {question}")
                st.write(f"**A:** {response}")

# Footer
st.markdown("---")
st.markdown("Built with ❤️ for fantasy football domination | Data updates every 30 seconds when auto-refresh is enabled")