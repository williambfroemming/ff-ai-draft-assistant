import pandas as pd

def load_player_pool(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(columns={
        'PLAYER NAME': 'Player',
        'TEAM': 'Team',
        'POS': 'Position',
        'BYE WEEK': 'Bye_Week'
    })
    df = df[['Player', 'Team', 'Position', 'Bye_Week']]
    df['Position'] = df['Position'].str.extract(r'([A-Z]+)')
    df = df.dropna(subset=['Player'])
    return df