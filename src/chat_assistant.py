import os
import openai
import pandas as pd
from typing import Dict, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Required for openai>=1.0.0
try:
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}")
    client = None

def calculate_positional_scarcity(available_players: pd.DataFrame, position: str, top_n: int = 20) -> str:
    """Calculate scarcity metrics for a given position."""
    pos_players = available_players[available_players['Position'] == position]
    total_pos_available = len(pos_players)
    
    if total_pos_available == 0:
        return f"No {position} players available"
    
    scarcity_level = "High" if total_pos_available <= 5 else "Medium" if total_pos_available <= 15 else "Low"
    return f"{position} scarcity: {scarcity_level} ({total_pos_available} available)"

def analyze_draft_trends(draft_board: pd.DataFrame, lookback_picks: int = 10) -> Dict[str, str]:
    """Analyze recent draft trends with detailed breakdown."""
    if draft_board.empty or len(draft_board) < lookback_picks:
        return {
            "summary": "Insufficient draft data for trend analysis",
            "recent_picks": "No recent picks available",
            "position_trends": "No position data available",
            "spending_trends": "No spending data available",
            "manager_activity": "No manager data available"
        }
    
    recent_picks = draft_board.tail(lookback_picks).copy()
    
    # Detailed recent picks breakdown
    recent_picks_detail = []
    for idx, pick in recent_picks.iterrows():
        pick_detail = f"• {pick['Player']} ({pick['Position']}) - ${pick.get('Price', 0):.0f} to {pick['Drafted By']}"
        recent_picks_detail.append(pick_detail)
    
    # Position trends
    pos_counts = recent_picks['Position'].value_counts()
    trending_pos = pos_counts.index[0] if len(pos_counts) > 0 else "Unknown"
    position_breakdown = []
    for pos, count in pos_counts.head(4).items():
        position_breakdown.append(f"{pos}: {count}")
    
    # Price trends
    if 'Price' in recent_picks.columns:
        avg_price = recent_picks['Price'].mean()
        max_price = recent_picks['Price'].max()
        min_price = recent_picks['Price'].min()
        spending_detail = f"Avg: ${avg_price:.0f}, Range: ${min_price:.0f}-${max_price:.0f}"
    else:
        spending_detail = "Price data not available"
    
    # Manager activity
    manager_picks = recent_picks['Drafted By'].value_counts()
    active_managers = len(manager_picks)
    most_active = manager_picks.index[0] if len(manager_picks) > 0 else "Unknown"
    
    return {
        "summary": f"{trending_pos} is trending ({pos_counts.iloc[0]} of last {lookback_picks}), avg price ${avg_price:.0f}",
        "recent_picks": f"LAST {lookback_picks} PICKS:\n" + "\n".join(recent_picks_detail),
        "position_trends": f"Position breakdown: {', '.join(position_breakdown)}",
        "spending_trends": f"Spending trends: {spending_detail}",
        "manager_activity": f"{active_managers} managers active, {most_active} most active ({manager_picks.iloc[0]} picks)"
    }

def get_detailed_draft_context(draft_board: pd.DataFrame, lookback_picks: int = 15) -> str:
    """Get comprehensive recent draft activity for AI context."""
    if draft_board.empty:
        return "No draft activity to analyze"
    
    # Get the most recent picks with full details
    recent_count = min(lookback_picks, len(draft_board))
    recent_picks = draft_board.tail(recent_count).copy()
    
    # Create detailed pick-by-pick breakdown
    pick_details = []
    pick_details.append(f"RECENT DRAFT ACTIVITY (Last {recent_count} picks):")
    pick_details.append("=" * 50)
    
    for i, (idx, pick) in enumerate(recent_picks.iterrows(), 1):
        price = pick.get('Price', 0)
        position = pick.get('Position', 'Unknown')
        player = pick.get('Player', 'Unknown')
        manager = pick.get('Drafted By', 'Unknown')
        
        pick_details.append(f"{recent_count - i + 1} picks ago: {player} ({position}) - ${price:.0f} → {manager}")
    
    # Add trend analysis
    trends = analyze_draft_trends(draft_board, lookback_picks)
    pick_details.append("")
    pick_details.append("TREND ANALYSIS:")
    pick_details.append(f"• {trends['position_trends']}")
    pick_details.append(f"• {trends['spending_trends']}")
    pick_details.append(f"• {trends['manager_activity']}")
    
    # Add position run detection
    pick_details.append("")
    pick_details.append("POSITION RUN ALERTS:")
    for pos in ['QB', 'RB', 'WR', 'TE']:
        run_info = analyze_positional_runs(draft_board, pos, lookback_picks)
        pick_details.append(f"• {run_info}")
    
    return "\n".join(pick_details)

def get_budget_percentile(remaining_budget: float, opponent_budgets: list) -> str:
    """Calculate budget percentile compared to opponents."""
    if not opponent_budgets:
        return "No opponent budget data available"
    
    better_than = sum(1 for budget in opponent_budgets if remaining_budget > budget)
    percentile = (better_than / len(opponent_budgets)) * 100
    
    if percentile >= 80:
        return f"Strong budget position (top {100-percentile:.0f}%)"
    elif percentile >= 50:
        return f"Average budget position ({percentile:.0f}th percentile)"
    else:
        return f"Weak budget position (bottom {100-percentile:.0f}%)"

def summarize_opponents_rosters(draft_board: pd.DataFrame, my_name: str) -> str:
    """Create a concise summary of opponent rosters."""
    summaries = []
    grouped = draft_board.groupby("Drafted By")

    for manager, picks in grouped:
        if manager.strip().lower() == my_name.strip().lower():
            continue
        
        # Position breakdown
        pos_counts = picks['Position'].value_counts()
        pos_summary = ", ".join([f"{pos}:{count}" for pos, count in pos_counts.items()])
        
        # Key players (highest priced)
        top_picks = picks.nlargest(3, 'Price') if 'Price' in picks.columns else picks.head(3)
        key_players = ", ".join(top_picks['Player'].tolist())
        
        total_spent = picks['Price'].sum() if 'Price' in picks.columns else 0
        
        summaries.append(f"{manager}: {pos_summary} | Key: {key_players} | Spent: ${total_spent:.0f}")

    return "\n".join(summaries) if summaries else "No opponent data available"

def get_contextual_advice(my_team: dict, draft_stage: str) -> str:
    """Provide stage-specific advice based on draft progress."""
    roster_size = my_team["roster"].shape[0]
    budget = my_team["remaining_budget"]
    
    if roster_size <= 3:
        return "Early draft: Focus on securing elite talent at RB/WR. Don't chase QB early."
    elif roster_size <= 8:
        return "Mid draft: Balance value with need. Consider positional runs and handcuffs."
    elif budget <= 20:
        return "Late draft: Focus on value picks, sleepers, and filling mandatory positions."
    else:
        return "Flexible stage: Mix of stars and scrubs strategy recommended."

def ask_ai_assistant(prompt: str,
                     my_team: dict,
                     draft_board: pd.DataFrame,
                     available_players: pd.DataFrame,
                     my_name: str = "Bill",
                     include_analysis: bool = True) -> str:
    """
    Enhanced AI assistant with better context and analysis.
    
    Args:
        prompt: User's question
        my_team: Current team data
        draft_board: All draft picks
        available_players: Remaining player pool
        my_name: Manager name
        include_analysis: Whether to include advanced analysis
    """
    
    if client is None:
        return "AI assistant unavailable - OpenAI client not configured"
    
    try:
        # Basic team info
        team_roster = my_team["roster"][["Player", "Position", "Price"]].to_string(index=False) if not my_team["roster"].empty else "No players drafted"
        budget = my_team["remaining_budget"]
        needs = my_team["position_counts"]
        
        # Top available players
        available_summary = available_players.head(15)[["Player", "Position"]].to_string(index=False) if not available_players.empty else "No players available"
        
        # Enhanced context with detailed draft activity
        context_parts = [
            "You are an expert fantasy football auction draft assistant analyzing REAL draft data.",
            "The data below shows ACTUAL recent picks and trends from this specific draft.",
            "Use this information to provide specific, data-driven advice.",
            "",
            f"CURRENT SITUATION:",
            f"Manager: {my_name}",
            f"Players drafted: {my_team['roster'].shape[0]}",
            f"Remaining budget: ${budget}",
            f"Total picks made: {len(draft_board)}",
            "",
            f"MY CURRENT ROSTER:",
            team_roster,
            "",
            f"POSITION COUNTS: {dict(needs)}",
            "",
            f"TOP AVAILABLE PLAYERS:",
            available_summary,
        ]
        
        if include_analysis and len(draft_board) > 0:
            # Add comprehensive recent draft analysis
            detailed_context = get_detailed_draft_context(draft_board, 15)
            context_parts.extend([
                "",
                detailed_context,
                "",
            ])
            
            # Add opponent analysis
            opponent_rosters = summarize_opponents_rosters(draft_board, my_name)
            contextual_advice = get_contextual_advice(my_team, "mid")
            
            # Position scarcity analysis
            scarcity_analysis = []
            for pos in ['QB', 'RB', 'WR', 'TE']:
                scarcity = calculate_positional_scarcity(available_players, pos)
                scarcity_analysis.append(scarcity)
            
            context_parts.extend([
                f"CONTEXTUAL ADVICE: {contextual_advice}",
                "",
                f"POSITION SCARCITY:",
                "\n".join(scarcity_analysis),
                "",
                f"OPPONENT SUMMARIES:",
                opponent_rosters,
            ])
        
        # Add strategic guidelines
        context_parts.extend([
            "",
            "STRATEGIC GUIDELINES:",
            "- Analyze the ACTUAL recent picks shown above",
            "- Consider how recent trends affect player values and availability",
            "- Factor in opponent behavior and spending patterns",
            "- Account for positional runs and market timing",
            "- Provide specific recommendations based on the real data",
            "",
            "IMPORTANT: Base your advice on the actual draft data provided above.",
            "Reference specific recent picks and trends when making recommendations.",
        ])
        
        context = "\n".join(context_parts)
        
        # Prepare messages
        messages = [
            {
                "role": "system", 
                "content": context
            },
            {
                "role": "user", 
                "content": prompt
            }
        ]
        
        # Make API call with error handling
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.3,
            max_tokens=800,
            timeout=30
        )
        
        return response.choices[0].message.content
        
    except openai.RateLimitError:
        return "AI service temporarily unavailable due to rate limits. Please try again in a moment."
    except openai.APITimeoutError:
        return "AI service timed out. Please try again with a simpler question."
    except openai.APIError as e:
        logger.error(f"OpenAI API error: {e}")
        return f"AI service error. Please try again later."
    except Exception as e:
        logger.error(f"Unexpected error in AI assistant: {e}")
        return "Sorry, I encountered an error. Please try rephrasing your question."

def get_quick_recommendation(my_team: dict, 
                           available_players: pd.DataFrame, 
                           recommendation_type: str = "next_pick") -> str:
    """
    Get quick recommendations without full AI processing.
    
    Args:
        my_team: Current team data
        available_players: Available player pool
        recommendation_type: Type of recommendation needed
    """
    
    try:
        budget = my_team["remaining_budget"]
        needs = my_team["position_counts"]
        
        if recommendation_type == "next_pick":
            # Simple logic for next pick recommendation
            if needs.get('RB', 0) < 2 and budget > 50:
                rb_options = available_players[available_players['Position'] == 'RB'].head(3)
                if not rb_options.empty:
                    return f"Recommend targeting RB: {', '.join(rb_options['Player'].tolist())}"
            
            if needs.get('WR', 0) < 3 and budget > 30:
                wr_options = available_players[available_players['Position'] == 'WR'].head(3)
                if not wr_options.empty:
                    return f"Recommend targeting WR: {', '.join(wr_options['Player'].tolist())}"
            
            return "Focus on best available value plays"
            
        elif recommendation_type == "budget_alert":
            if budget < 10:
                return "⚠️ Critical: Budget very low - target $1-2 players only"
            elif budget < 25:
                return "⚠️ Warning: Limited budget - prioritize must-have positions"
            else:
                return "💰 Good budget flexibility for quality players"
                
        return "No specific recommendation available"
        
    except Exception as e:
        logger.error(f"Error in quick recommendation: {e}")
        return "Unable to generate recommendation"

# Utility functions for enhanced assistant
def get_player_suggestions_by_budget(available_players: pd.DataFrame, 
                                   budget_range: tuple,
                                   position: Optional[str] = None) -> pd.DataFrame:
    """Get player suggestions within a specific budget range."""
    # This would require auction values in your player pool
    # For now, return basic filtering
    filtered = available_players.copy()
    
    if position:
        filtered = filtered[filtered['Position'] == position]
    
    return filtered.head(10)

def analyze_positional_runs(draft_board: pd.DataFrame, position: str, lookback: int = 15) -> str:
    """Analyze if there's a positional run happening."""
    if len(draft_board) < lookback:
        return f"Insufficient data to analyze {position} runs"
    
    recent_picks = draft_board.tail(lookback)
    pos_picks = recent_picks[recent_picks['Position'] == position]
    
    if len(pos_picks) >= 4:
        recent_players = pos_picks.tail(4)['Player'].tolist()
        return f"MAJOR {position} RUN: {len(pos_picks)} picked in last {lookback} (Recent: {', '.join(recent_players)})"
    elif len(pos_picks) >= 3:
        return f"⚠️ {position} RUN DETECTED: {len(pos_picks)} {position}s picked in last {lookback} picks"
    elif len(pos_picks) >= 2:
        return f"📈 {position} heating up: {len(pos_picks)} picked recently"
    else:
        return f"✅ No {position} run currently"

def estimate_player_cost(player_name: str, position: str, tier: str = "mid") -> str:
    """Provide rough cost estimates based on position and tier."""
    # Simple estimation logic - would be better with actual auction values
    cost_ranges = {
        'QB': {'elite': '$25-35', 'mid': '$8-15', 'late': '$1-3'},
        'RB': {'elite': '$45-65', 'mid': '$20-35', 'late': '$5-12'},
        'WR': {'elite': '$40-60', 'mid': '$18-30', 'late': '$5-10'},
        'TE': {'elite': '$20-30', 'mid': '$8-15', 'late': '$1-5'},
        'DEF': {'elite': '$3-6', 'mid': '$1-3', 'late': '$1'},
    }
    
    return cost_ranges.get(position, {}).get(tier, 'Unknown')

def get_bye_week_analysis(my_team: dict) -> str:
    """Analyze bye week conflicts in current roster."""
    if 'Bye_Week' not in my_team['roster'].columns:
        return "Bye week data not available"
    
    bye_conflicts = my_team['roster'].groupby(['Position', 'Bye_Week']).size()
    conflicts = bye_conflicts[bye_conflicts > 1]
    
    if conflicts.empty:
        return "✅ No bye week conflicts detected"
    else:
        conflict_str = ", ".join([f"{pos} Week {week} ({count} players)" 
                                for (pos, week), count in conflicts.items()])
        return f"⚠️ Bye week conflicts: {conflict_str}"

def suggest_handcuffs(my_team: dict, available_players: pd.DataFrame) -> str:
    """Suggest handcuff pickups for current RBs."""
    my_rbs = my_team['roster'][my_team['roster']['Position'] == 'RB']
    
    if my_rbs.empty:
        return "No RBs to handcuff"
    
    # This would require team data to match handcuffs
    # For now, provide generic advice
    rb_teams = my_rbs.get('Team', []).tolist() if 'Team' in my_rbs.columns else []
    
    if rb_teams:
        return f"Consider handcuffs for your RBs from: {', '.join(set(rb_teams))}"
    else:
        return "Consider targeting backup RBs from strong rushing offenses"

# Enhanced error handling and validation
def validate_inputs(my_team: dict, draft_board: pd.DataFrame, available_players: pd.DataFrame) -> tuple:
    """Validate inputs and return any warnings."""
    warnings = []
    
    if my_team['remaining_budget'] < 0:
        warnings.append("Negative budget detected - check calculations")
    
    if draft_board.empty:
        warnings.append("No draft data available")
    
    if available_players.empty:
        warnings.append("No available players found")
    
    # Check for required columns
    required_draft_cols = ['Player', 'Position', 'Price', 'Drafted By']
    missing_cols = [col for col in required_draft_cols if col not in draft_board.columns]
    if missing_cols:
        warnings.append(f"Missing draft board columns: {missing_cols}")
    
    return warnings

def format_ai_response(response: str) -> str:
    """Format AI response for better readability."""
    # Add bullet points and formatting
    lines = response.split('\n')
    formatted_lines = []
    
    for line in lines:
        line = line.strip()
        if line:
            # Add emphasis to key terms
            line = line.replace('RECOMMENDATION:', '**RECOMMENDATION:**')
            line = line.replace('WARNING:', '⚠️ **WARNING:**')
            line = line.replace('STRATEGY:', '🎯 **STRATEGY:**')
            formatted_lines.append(line)
    
    return '\n\n'.join(formatted_lines)

# Main enhanced function with all improvements
def ask_ai_assistant_v2(prompt: str,
                       my_team: dict,
                       draft_board: pd.DataFrame,
                       available_players: pd.DataFrame,
                       my_name: str = "Bill",
                       context_level: str = "full") -> str:
    """
    Version 2 of AI assistant with comprehensive enhancements and detailed draft analysis.
    
    Args:
        prompt: User's question
        my_team: Current team data
        draft_board: All draft picks
        available_players: Remaining player pool
        my_name: Manager name
        context_level: "basic", "standard", or "full"
    """
    
    if client is None:
        return "🚫 AI assistant unavailable - OpenAI API key not configured"
    
    # Validate inputs
    warnings = validate_inputs(my_team, draft_board, available_players)
    if warnings:
        warning_text = " | ".join(warnings)
        logger.warning(f"Input validation warnings: {warning_text}")
    
    try:
        # Core team information
        roster_display = my_team["roster"][["Player", "Position", "Price"]].to_string(index=False) if not my_team["roster"].empty else "No players drafted yet"
        budget = my_team["remaining_budget"]
        position_counts = dict(my_team["position_counts"])
        draft_progress = len(draft_board)
        
        # Available players summary
        top_available = available_players.head(20)[["Player", "Position"]].to_string(index=False) if not available_players.empty else "No available players"
        
        # Build context based on level
        context_sections = [
            "You are an expert fantasy football auction draft strategist analyzing REAL draft data.",
            "Use the ACTUAL recent picks and trends below to provide specific, data-driven advice.",
            "Reference specific players and trends from the recent activity when making recommendations.",
            "",
            f"DRAFT STATUS:",
            f"• Manager: {my_name}",
            f"• Total picks made league-wide: {draft_progress}",
            f"• My players drafted: {my_team['roster'].shape[0]}",
            f"• Remaining budget: ${budget:.2f}",
            "",
            f"MY CURRENT ROSTER:",
            roster_display,
            "",
            f"POSITION BREAKDOWN: {position_counts}",
            "",
            f"TOP AVAILABLE PLAYERS:",
            top_available,
        ]
        
        if context_level in ["standard", "full"] and len(draft_board) > 0:
            # Add detailed recent draft activity
            detailed_context = get_detailed_draft_context(draft_board, 15)
            context_sections.extend([
                "",
                detailed_context,
            ])
        
        if context_level == "full":
            # Add comprehensive analysis
            opponent_summary = summarize_opponents_rosters(draft_board, my_name)
            contextual_advice = get_contextual_advice(my_team, "current")
            bye_analysis = get_bye_week_analysis(my_team)
            handcuff_suggestions = suggest_handcuffs(my_team, available_players)
            
            context_sections.extend([
                "",
                f"STRATEGIC CONTEXT:",
                f"• {contextual_advice}",
                f"• {bye_analysis}",
                f"• {handcuff_suggestions}",
                "",
                f"OPPONENT ANALYSIS:",
                opponent_summary,
                "",
                f"SCARCITY ANALYSIS:",
            ])
            
            # Add scarcity for each position
            for pos in ['QB', 'RB', 'WR', 'TE']:
                scarcity = calculate_positional_scarcity(available_players, pos)
                context_sections.append(f"• {scarcity}")
        
        # Add strategic guidelines
        context_sections.extend([
            "",
            "STRATEGIC PRINCIPLES:",
            "• Analyze the ACTUAL recent picks and trends shown above",
            "• Reference specific players mentioned in recent activity",
            "• Consider how recent positional runs affect strategy",
            "• Factor in opponent spending patterns and behavior",
            "• Provide data-driven recommendations based on real trends",
            "",
            "CRITICAL: Use the specific draft data provided above in your analysis.",
            "Mention recent picks, trends, and patterns when relevant.",
        ])
        
        full_context = "\n".join(context_sections)
        
        # Create messages
        messages = [
            {"role": "system", "content": full_context},
            {"role": "user", "content": prompt}
        ]
        
        # API call with enhanced error handling
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.2,  # Lower for more consistent advice
            max_tokens=1000,
            timeout=45
        )
        
        raw_response = response.choices[0].message.content
        formatted_response = format_ai_response(raw_response)
        
        # Add warnings if any
        if warnings:
            formatted_response = f"⚠️ *Data warnings: {' | '.join(warnings)}*\n\n{formatted_response}"
        
        return formatted_response
        
    except openai.RateLimitError:
        return "🔄 AI service busy - please wait a moment and try again."
    except openai.APITimeoutError:
        return "⏱️ Request timed out - try a shorter question or check connection."
    except openai.AuthenticationError:
        return "🔑 API authentication failed - check OpenAI API key configuration."
    except openai.APIError as e:
        logger.error(f"OpenAI API error: {e}")
        return f"🚫 AI service error: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in AI assistant: {e}")
        return f"❌ Unexpected error occurred. Please try again or contact support."

# Backward compatibility - use enhanced version by default
def ask_ai_assistant(*args, **kwargs):
    """Main AI assistant function with backward compatibility."""
    return ask_ai_assistant_v2(*args, **kwargs)