"""
Fuzzy Search for Pandas DataFrame with JSON-encoded tags.

This module provides fuzzy search functionality for DataFrames where:
- One column contains searchable names/text
- Another column contains JSON with semicolon-separated values (e.g., "cuisine": "italian;pizza")
"""

import pandas as pd
import json
from difflib import SequenceMatcher
from typing import List, Dict, Optional


class DataFrameFuzzySearch:
    """
    Fuzzy search engine for pandas DataFrames with JSON-encoded tags.

    Example usage:
        df = pd.DataFrame({
            'name': ['Pizza Palace', 'Burger Kingdom'],
            'tags': [
                '{"cuisine": "italian;pizza", "price": "$$"}',
                '{"cuisine": "american;fast_food", "price": "$"}'
            ]
        })

        searcher = DataFrameFuzzySearch(df, name_col='name', tags_col='tags', tag_key='cuisine')
        results = searcher.search('italian', threshold=70)
    """

    def __init__(self, df: pd.DataFrame, name_col: str = 'name',
                 tags_col: str = 'tags', tag_key: str = 'cuisine'):
        """
        Initialize the fuzzy search engine.

        Args:
            df: The DataFrame to search
            name_col: Name of the column containing searchable text
            tags_col: Name of the column containing JSON data
            tag_key: Key in the JSON object that contains semicolon-separated values
        """
        self.df = df.copy()
        self.name_col = name_col
        self.tags_col = tags_col
        self.tag_key = tag_key

    def _extract_tag_values(self, tags_json: str) -> List[str]:
        """Extract tag values from JSON column (semicolon-separated)."""
        try:
            tags_dict = json.loads(tags_json)
            value_str = tags_dict.get(self.tag_key, '')
            if value_str:
                return [v.strip() for v in value_str.split(';') if v.strip()]
            return []
        except (json.JSONDecodeError, TypeError, AttributeError):
            return []

    @staticmethod
    def _similarity_score(str1: str, str2: str) -> int:
        """Calculate similarity score between two strings (0-100)."""
        return round(SequenceMatcher(None, str1.lower(), str2.lower()).ratio() * 100)

    @staticmethod
    def _partial_similarity(query: str, text: str) -> int:
        """Calculate best partial match similarity with substring detection."""
        query_lower = query.lower()
        text_lower = text.lower()

        # Perfect substring matches
        if query_lower in text_lower or text_lower in query_lower:
            return 100

        # Calculate regular similarity
        regular_score = DataFrameFuzzySearch._similarity_score(query, text)

        # Try sliding window for partial matching
        best_score = regular_score
        query_len = len(query)

        if query_len <= len(text):
            for i in range(len(text) - query_len + 1):
                substring = text[i:i + query_len]
                score = DataFrameFuzzySearch._similarity_score(query, substring)
                best_score = max(best_score, score)

        return best_score

    def search(self, query: str, threshold: int = 70,
               include_details: bool = True) -> pd.DataFrame:
        """
        Perform fuzzy search on name column and tag values.

        Args:
            query: Search string
            threshold: Minimum similarity score (0-100) to include in results
            include_details: If True, include score breakdown and matched values

        Returns:
            DataFrame with matching rows, sorted by relevance
        """
        results = []

        for idx, row in self.df.iterrows():
            # Search in name column
            name_score = self._partial_similarity(query, str(row[self.name_col]))

            # Search in tag values
            tag_values = self._extract_tag_values(row[self.tags_col])
            tag_matches = []

            for tag_value in tag_values:
                score = self._partial_similarity(query, tag_value)
                if score >= threshold:
                    tag_matches.append((tag_value, score))

            max_tag_score = max([score for _, score in tag_matches]) if tag_matches else 0
            matched_tags = [tag for tag, _ in tag_matches]

            # Best overall score
            best_score = max(name_score, max_tag_score)

            if best_score >= threshold:
                results.append({
                    'index': idx,
                    'score': best_score,
                    'name_score': name_score,
                    'tag_score': max_tag_score,
                    'matched_tags': matched_tags,
                    'all_tags': tag_values
                })

        # Sort by score (descending)
        results = sorted(results, key=lambda x: x['score'], reverse=True)

        if not results:
            return pd.DataFrame()

        # Create result DataFrame
        result_df = self.df.loc[[r['index'] for r in results]].copy()

        if include_details:
            result_df['match_score'] = [r['score'] for r in results]
            result_df['name_score'] = [r['name_score'] for r in results]
            result_df['tag_score'] = [r['tag_score'] for r in results]
            result_df['matched_tags'] = [r['matched_tags'] for r in results]

        return result_df


# Example usage and demonstration
if __name__ == '__main__':
    # Sample data
    data = {
        'id': [1, 2, 3, 4, 5, 6],
        'name': ['Pizza Palace', 'Burger Kingdom', 'Sushi Bar',
                 'Taco Fiesta', 'Pasta House', 'Ice Cream Parlor'],
        'tags': [
            '{"cuisine": "italian;pizza", "price": "$$"}',
            '{"cuisine": "american;fast_food", "price": "$"}',
            '{"cuisine": "japanese;sushi", "price": "$$$"}',
            '{"cuisine": "mexican;tex_mex", "price": "$$"}',
            '{"cuisine": "italian;pasta;ice_cream", "price": "$$"}',
            '{"cuisine": "ice_cream;dessert;frozen_yogurt", "price": "$"}'
        ],
        'rating': [4.5, 3.8, 4.7, 4.2, 4.6, 4.0]
    }

    df = pd.DataFrame(data)

    print("Original DataFrame:")
    print(df[['id', 'name', 'tags']])
    print("\n" + "=" * 80 + "\n")

    # Create searcher
    searcher = DataFrameFuzzySearch(df, name_col='name', tags_col='tags', tag_key='cuisine')

    # Test searches
    test_queries = [
        ('italian', 70),
        ('ice', 70),
        ('sush', 70),
        ('mex', 70),
        ('burger', 70),
    ]

    for query, threshold in test_queries:
        print(f"Search: '{query}' (threshold={threshold})")
        results = searcher.search(query, threshold=threshold)

        if not results.empty:
            display_cols = ['name', 'match_score', 'name_score', 'tag_score', 'matched_tags']
            print(results[display_cols].to_string())
        else:
            print("No matches found")
        print("\n" + "-" * 80 + "\n")

    # Example without details
    print("Search without score details:")
    results = searcher.search('italian', threshold=70, include_details=False)
    print(results[['id', 'name', 'rating']])