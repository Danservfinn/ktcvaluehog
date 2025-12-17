"""
Market Sentiment Client
Fetches sentiment data from Reddit and other sources.
"""

import requests
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import pandas as pd
import re

logger = logging.getLogger(__name__)


class RedditSentimentClient:
    """
    Fetch fantasy football sentiment from Reddit.

    Uses Reddit's public JSON API (no authentication required).
    """

    BASE_URL = "https://www.reddit.com"
    SUBREDDITS = [
        'DynastyFF',
        'fantasyfootball',
        'Fantasy_Football',
        'fantasyfootballadvice'
    ]
    TIMEOUT = 30

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; DynastyEdge/1.0; +https://github.com/dynastyedge)'
        })

    def _get_json(self, url: str) -> Any:
        """Fetch JSON from Reddit."""
        try:
            response = self.session.get(f"{url}.json", timeout=self.TIMEOUT)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Reddit API error: {e}")
            return None

    def search_player_mentions(self, player_name: str, limit: int = 25) -> List[Dict]:
        """
        Search for mentions of a player across fantasy subreddits.

        Args:
            player_name: Player name to search
            limit: Max posts to return per subreddit

        Returns:
            List of post dicts with sentiment analysis
        """
        mentions = []

        for subreddit in self.SUBREDDITS:
            try:
                # Search subreddit
                search_url = f"{self.BASE_URL}/r/{subreddit}/search"
                params = {
                    'q': player_name,
                    'restrict_sr': 'on',
                    'sort': 'new',
                    'limit': limit
                }
                url = f"{search_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
                data = self._get_json(url)

                if not data or 'data' not in data:
                    continue

                for post in data['data'].get('children', []):
                    post_data = post.get('data', {})
                    mentions.append({
                        'subreddit': subreddit,
                        'title': post_data.get('title', ''),
                        'text': post_data.get('selftext', ''),
                        'score': post_data.get('score', 0),
                        'upvote_ratio': post_data.get('upvote_ratio', 0.5),
                        'num_comments': post_data.get('num_comments', 0),
                        'created_utc': post_data.get('created_utc', 0),
                        'url': post_data.get('url', ''),
                        'player_name': player_name
                    })
            except Exception as e:
                logger.warning(f"Error searching {subreddit}: {e}")
                continue

        return mentions

    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Simple rule-based sentiment analysis.

        Returns sentiment score (-1 to 1) and keywords detected.
        """
        text_lower = text.lower()

        # Positive indicators
        positive_words = [
            'breakout', 'buy', 'sleeper', 'undervalued', 'must-own', 'boom',
            'elite', 'target', 'ascending', 'upside', 'steal', 'value',
            'stash', 'hold', 'confident', 'bullish', 'love', 'get', 'grab'
        ]

        # Negative indicators
        negative_words = [
            'bust', 'sell', 'overvalued', 'avoid', 'fade', 'declining',
            'concern', 'worried', 'injury', 'drop', 'bearish', 'hate',
            'overpay', 'dump', 'panic', 'falling', 'washed', 'done'
        ]

        # Count matches
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        total = positive_count + negative_count
        if total == 0:
            sentiment = 0.0
        else:
            sentiment = (positive_count - negative_count) / total

        # Detect keywords
        keywords = []
        keywords.extend([w for w in positive_words if w in text_lower])
        keywords.extend([w for w in negative_words if w in text_lower])

        return {
            'sentiment': sentiment,
            'positive_count': positive_count,
            'negative_count': negative_count,
            'keywords': keywords[:10],
            'classification': 'positive' if sentiment > 0.2 else 'negative' if sentiment < -0.2 else 'neutral'
        }

    def get_player_sentiment(self, player_name: str) -> Dict[str, Any]:
        """
        Get aggregated sentiment for a player.

        Args:
            player_name: Player name to analyze

        Returns:
            Aggregated sentiment data
        """
        mentions = self.search_player_mentions(player_name, limit=50)

        if not mentions:
            return {
                'player': player_name,
                'sentiment_score': 0,
                'mention_count': 0,
                'classification': 'unknown',
                'buzz_score': 0
            }

        # Analyze each mention
        sentiments = []
        total_score = 0
        total_comments = 0

        for mention in mentions:
            analysis = self.analyze_sentiment(f"{mention['title']} {mention['text']}")
            sentiments.append(analysis)
            total_score += mention['score']
            total_comments += mention['num_comments']

        # Aggregate
        avg_sentiment = sum(s['sentiment'] for s in sentiments) / len(sentiments)
        positive_pct = sum(1 for s in sentiments if s['classification'] == 'positive') / len(sentiments)
        negative_pct = sum(1 for s in sentiments if s['classification'] == 'negative') / len(sentiments)

        # Calculate buzz score (engagement)
        buzz_score = min(100, (len(mentions) * 2 + total_comments / 10 + total_score / 100))

        return {
            'player': player_name,
            'sentiment_score': round(avg_sentiment, 3),
            'mention_count': len(mentions),
            'positive_pct': round(positive_pct * 100, 1),
            'negative_pct': round(negative_pct * 100, 1),
            'classification': 'positive' if avg_sentiment > 0.1 else 'negative' if avg_sentiment < -0.1 else 'neutral',
            'buzz_score': round(buzz_score, 1),
            'total_engagement': total_score + total_comments,
            'analyzed_at': datetime.now().isoformat()
        }

    def get_trending_discussions(self, subreddit: str = 'DynastyFF', limit: int = 25) -> List[Dict]:
        """Get trending discussions from a subreddit."""
        url = f"{self.BASE_URL}/r/{subreddit}/hot"
        data = self._get_json(f"{url}?limit={limit}")

        if not data or 'data' not in data:
            return []

        posts = []
        for post in data['data'].get('children', []):
            post_data = post.get('data', {})
            posts.append({
                'title': post_data.get('title', ''),
                'score': post_data.get('score', 0),
                'num_comments': post_data.get('num_comments', 0),
                'url': f"https://reddit.com{post_data.get('permalink', '')}",
                'created': datetime.fromtimestamp(post_data.get('created_utc', 0)).isoformat()
            })

        return posts


class SentimentNeo4jLoader:
    """Load sentiment data into Neo4j."""

    def __init__(self, driver):
        self.driver = driver
        self.reddit = RedditSentimentClient()

    def update_player_sentiment(self, player_name: str) -> Dict:
        """Update sentiment for a specific player."""
        sentiment = self.reddit.get_player_sentiment(player_name)

        with self.driver.session() as session:
            session.run("""
                MATCH (p:Player)
                WHERE toLower(p.name) = toLower($name)
                SET p.reddit_sentiment = $sentiment,
                    p.reddit_buzz = $buzz,
                    p.reddit_mentions = $mentions,
                    p.sentiment_classification = $classification,
                    p.sentiment_updated = datetime()
            """, {
                'name': player_name,
                'sentiment': sentiment['sentiment_score'],
                'buzz': sentiment['buzz_score'],
                'mentions': sentiment['mention_count'],
                'classification': sentiment['classification']
            })

        return sentiment

    def update_top_players_sentiment(self, min_ktc: int = 2000, limit: int = 100) -> int:
        """Update sentiment for top valued players."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Player)
                WHERE p.ktc_value >= $min_ktc
                  AND p.position IN ['QB', 'RB', 'WR', 'TE']
                RETURN p.name as name
                ORDER BY p.ktc_value DESC
                LIMIT $limit
            """, {'min_ktc': min_ktc, 'limit': limit})

            players = [r['name'] for r in result]

        count = 0
        for player in players:
            try:
                self.update_player_sentiment(player)
                count += 1
                logger.info(f"Updated sentiment for {player}")
            except Exception as e:
                logger.warning(f"Failed to update sentiment for {player}: {e}")

        return count

    def get_sentiment_signals(self) -> pd.DataFrame:
        """Get sentiment-based trading signals."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Player)
                WHERE p.reddit_sentiment IS NOT NULL
                  AND p.ktc_value > 1000
                WITH p,
                     // Combine sentiment with edge signal
                     CASE
                         WHEN p.reddit_sentiment > 0.3 AND p.edge_signal IN ['BUY', 'STRONG_BUY']
                         THEN 'STRONG_BUY_CONFIRMED'
                         WHEN p.reddit_sentiment < -0.3 AND p.edge_signal IN ['SELL', 'STRONG_SELL']
                         THEN 'STRONG_SELL_CONFIRMED'
                         WHEN p.reddit_sentiment > 0.3 AND p.edge_signal IN ['SELL', 'STRONG_SELL']
                         THEN 'CONTRARIAN_BUY'
                         WHEN p.reddit_sentiment < -0.3 AND p.edge_signal IN ['BUY', 'STRONG_BUY']
                         THEN 'CONTRARIAN_SELL'
                         ELSE 'NEUTRAL'
                     END as combined_signal
                RETURN p.name as player,
                       p.position as position,
                       p.ktc_value as ktc_value,
                       p.edge_signal as edge_signal,
                       p.reddit_sentiment as sentiment,
                       p.reddit_buzz as buzz,
                       p.sentiment_classification as sentiment_class,
                       combined_signal
                ORDER BY ABS(p.reddit_sentiment) DESC
            """)
            return pd.DataFrame([dict(r) for r in result])


def run_sentiment_update(driver, min_ktc: int = 3000) -> Dict[str, Any]:
    """Run sentiment update for top players."""
    loader = SentimentNeo4jLoader(driver)

    # Update sentiment
    count = loader.update_top_players_sentiment(min_ktc=min_ktc, limit=50)

    # Get signals
    signals = loader.get_sentiment_signals()

    return {
        'players_updated': count,
        'sentiment_signals': signals
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test Reddit client
    client = RedditSentimentClient()

    # Test player sentiment
    sentiment = client.get_player_sentiment("Ja'Marr Chase")
    print(f"\nJa'Marr Chase Sentiment:")
    print(sentiment)

    # Test trending discussions
    trending = client.get_trending_discussions('DynastyFF', limit=5)
    print(f"\nTrending on r/DynastyFF:")
    for post in trending:
        print(f"  - {post['title'][:60]}... ({post['score']} pts)")
