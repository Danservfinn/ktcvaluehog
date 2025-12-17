"""
Thoth - Graph Explorer
=======================
Explore the Neo4j knowledge graph relationships.
"""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.components.design_system import (
    apply_thoth_style, render_thoth_header, render_thoth_footer,
    COLORS
)

st.set_page_config(page_title="Graph Explorer - Thoth", page_icon="🔮", layout="wide")
apply_thoth_style()


@st.cache_resource
def get_driver():
    """Get Neo4j driver."""
    from neo4j import GraphDatabase
    uri = st.secrets.get("neo4j_uri", "bolt://localhost:7687")
    return GraphDatabase.driver(uri, auth=None)


@st.cache_data(ttl=3600)
def get_graph_stats():
    """Get overall graph statistics."""
    driver = get_driver()

    with driver.session() as session:
        # Node counts
        node_result = session.run("""
            MATCH (n)
            WITH labels(n)[0] as label, count(n) as count
            RETURN label, count
            ORDER BY count DESC
        """)
        nodes = {r['label']: r['count'] for r in node_result}

        # Relationship counts
        rel_result = session.run("""
            MATCH ()-[r]->()
            WITH type(r) as type, count(r) as count
            RETURN type, count
            ORDER BY count DESC
        """)
        rels = {r['type']: r['count'] for r in rel_result}

    return nodes, rels


def get_player_connections(player_name: str):
    """Get all connections for a player."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)
            WHERE toLower(p.name) CONTAINS toLower($name)
            WITH p LIMIT 1

            OPTIONAL MATCH (p)-[r]->(n)
            WITH p, collect({type: type(r), direction: 'outgoing', target: labels(n)[0], name: n.name}) as outgoing

            OPTIONAL MATCH (p)<-[r2]-(m)
            WITH p, outgoing, collect({type: type(r2), direction: 'incoming', source: labels(m)[0], name: m.name}) as incoming

            RETURN p.name as player,
                   p.position as position,
                   p.current_team as team,
                   p.ktc_value as ktc_value,
                   p.edge_signal as signal,
                   outgoing,
                   incoming
        """, {'name': player_name})
        return result.single()


def get_team_graph(team: str):
    """Get team subgraph."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (t:Team {team_abbr: $team})<-[:PLAYS_FOR]-(p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
            OPTIONAL MATCH (p)-[r:TARGETS_FROM|COMPETES_WITH]-(other:Player)
            WHERE (other)-[:PLAYS_FOR]->(t)
            RETURN p.name as player,
                   p.position as position,
                   p.ktc_value as ktc_value,
                   p.edge_signal as signal,
                   collect(DISTINCT {type: type(r), other: other.name}) as connections
            ORDER BY p.ktc_value DESC
        """, {'team': team})
        return [dict(r) for r in result]


def explore_relationship_type(rel_type: str, limit: int = 50):
    """Explore a specific relationship type."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run(f"""
            MATCH (a)-[r:{rel_type}]->(b)
            RETURN labels(a)[0] as source_type,
                   COALESCE(a.name, a.team_abbr, a.stage_id, toString(id(a))) as source,
                   type(r) as relationship,
                   labels(b)[0] as target_type,
                   COALESCE(b.name, b.team_abbr, b.stage_id, toString(id(b))) as target
            LIMIT $limit
        """, {'limit': limit})
        return pd.DataFrame([dict(r) for r in result])


def run_custom_query(query: str):
    """Run a custom Cypher query."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run(query)
        return pd.DataFrame([dict(r) for r in result])


def main():
    render_thoth_header("Graph Explorer", "Explore the Neo4j knowledge graph")

    # Graph Statistics
    st.markdown('<h3 class="section-header">Graph Statistics</h3>', unsafe_allow_html=True)

    try:
        nodes, rels = get_graph_stats()

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Node Types")
            for label, count in sorted(nodes.items(), key=lambda x: -x[1])[:10]:
                st.markdown(f"""
                <div style="display: flex; justify-content: space-between; padding: 0.25rem 0; border-bottom: 1px solid #E5E7EB;">
                    <span style="font-weight: 500;">{label}</span>
                    <span style="color: {COLORS['primary']}; font-weight: 600;">{count:,}</span>
                </div>
                """, unsafe_allow_html=True)

        with col2:
            st.markdown("#### Relationship Types")
            for rel_type, count in sorted(rels.items(), key=lambda x: -x[1])[:10]:
                st.markdown(f"""
                <div style="display: flex; justify-content: space-between; padding: 0.25rem 0; border-bottom: 1px solid #E5E7EB;">
                    <span style="font-weight: 500;">{rel_type}</span>
                    <span style="color: {COLORS['primary']}; font-weight: 600;">{count:,}</span>
                </div>
                """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Could not get graph stats: {e}")

    st.divider()

    # Explorer tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Player Network", "Team Graph", "Relationship Explorer", "Custom Query"])

    with tab1:
        st.markdown("#### Player Network")
        st.markdown("Search for a player to see their graph connections.")

        player_search = st.text_input("Search player", placeholder="Enter player name...", key="network_search")

        if player_search:
            try:
                result = get_player_connections(player_search)

                if result:
                    st.markdown(f"""
                    <div class="player-card" style="margin-bottom: 1rem;">
                        <span class="player-name">{result['player']}</span>
                        <span class="player-meta"> ({result['position']}, {result.get('team', 'FA')})</span>
                        <div style="margin-top: 0.5rem;">
                            KTC: {result.get('ktc_value', 0):,} | Signal: {result.get('signal', 'N/A')}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("**Outgoing Connections**")
                        outgoing = [c for c in result.get('outgoing', []) if c.get('name')]
                        if outgoing:
                            for conn in outgoing:
                                st.markdown(f"- **{conn['type']}** → {conn['target']}: {conn['name']}")
                        else:
                            st.markdown("*No outgoing connections*")

                    with col2:
                        st.markdown("**Incoming Connections**")
                        incoming = [c for c in result.get('incoming', []) if c.get('name')]
                        if incoming:
                            for conn in incoming:
                                st.markdown(f"- **{conn['type']}** ← {conn['source']}: {conn['name']}")
                        else:
                            st.markdown("*No incoming connections*")
                else:
                    st.info("Player not found. Try a different name.")
            except Exception as e:
                st.error(f"Error: {e}")

    with tab2:
        st.markdown("#### Team Graph")
        st.markdown("View player connections within a team.")

        teams = ['ARI', 'ATL', 'BAL', 'BUF', 'CAR', 'CHI', 'CIN', 'CLE',
                'DAL', 'DEN', 'DET', 'GB', 'HOU', 'IND', 'JAX', 'KC',
                'LAC', 'LAR', 'LV', 'MIA', 'MIN', 'NE', 'NO', 'NYG',
                'NYJ', 'PHI', 'PIT', 'SEA', 'SF', 'TB', 'TEN', 'WAS']

        selected_team = st.selectbox("Select Team", teams)

        if selected_team:
            try:
                team_data = get_team_graph(selected_team)

                if team_data:
                    st.markdown(f"#### {selected_team} Roster Network")

                    for player in team_data:
                        connections = player.get('connections', [])
                        conn_str = ", ".join([f"{c['type']} → {c['other']}" for c in connections if c.get('other')])

                        with st.expander(f"{player['player']} ({player['position']}) - KTC: {player.get('ktc_value', 0):,}"):
                            if conn_str:
                                st.markdown(f"**Team Connections:** {conn_str}")
                            else:
                                st.markdown("*No intra-team connections*")
                            st.markdown(f"**Signal:** {player.get('signal', 'N/A')}")
                else:
                    st.info("No players found for this team")
            except Exception as e:
                st.error(f"Error: {e}")

    with tab3:
        st.markdown("#### Relationship Explorer")
        st.markdown("Browse specific relationship types in the graph.")

        rel_types = ['PLAYS_FOR', 'TARGETS_FROM', 'COMPETES_WITH', 'AT_CAREER_STAGE',
                    'CHEMISTRY_WITH', 'HAD_SNAPSHOT', 'ROLE_IN', 'CAPTURES_OPPORTUNITY']

        selected_rel = st.selectbox("Relationship Type", rel_types)
        limit = st.slider("Max Results", 10, 100, 50)

        if selected_rel:
            try:
                rel_df = explore_relationship_type(selected_rel, limit)
                if not rel_df.empty:
                    st.dataframe(rel_df, use_container_width=True)
                else:
                    st.info(f"No {selected_rel} relationships found")
            except Exception as e:
                st.error(f"Error: {e}")

    with tab4:
        st.markdown("#### Custom Cypher Query")
        st.markdown("""
        <div class="warning-box">
            Only use READ queries. Write queries are not allowed.
        </div>
        """, unsafe_allow_html=True)

        default_query = """// Example: Top 10 players by KTC value
MATCH (p:Player)
WHERE p.ktc_value IS NOT NULL
RETURN p.name as player, p.position, p.ktc_value, p.edge_signal
ORDER BY p.ktc_value DESC
LIMIT 10"""

        query = st.text_area("Cypher Query", value=default_query, height=150)

        if st.button("Execute Query", type="primary"):
            if query.strip():
                try:
                    # Basic safety check
                    lower_query = query.lower()
                    if any(word in lower_query for word in ['delete', 'detach', 'remove', 'drop', 'create', 'merge', 'set']):
                        st.error("Write operations are not allowed in the explorer.")
                    else:
                        result_df = run_custom_query(query)
                        if not result_df.empty:
                            st.dataframe(result_df, use_container_width=True)
                            st.download_button("Download CSV", result_df.to_csv(index=False), "query_results.csv")
                        else:
                            st.info("Query returned no results")
                except Exception as e:
                    st.error(f"Query error: {e}")

        # Query examples
        with st.expander("Query Examples"):
            st.markdown("""
            **Top Players by Model Value:**
            ```cypher
            MATCH (p:Player)
            WHERE p.predicted_ktc_value IS NOT NULL
            RETURN p.name, p.position, p.ktc_value, p.predicted_ktc_value, p.edge_signal
            ORDER BY p.predicted_ktc_value DESC
            LIMIT 20
            ```

            **QB-WR Chemistry Pairs:**
            ```cypher
            MATCH (wr:Player)-[c:CHEMISTRY_WITH]->(qb:Player)
            WHERE c.cqi_score IS NOT NULL
            RETURN wr.name as receiver, qb.name as qb, c.cqi_score
            ORDER BY c.cqi_score DESC
            LIMIT 20
            ```

            **Players with Combine Data:**
            ```cypher
            MATCH (p:Player)
            WHERE p.combine_forty IS NOT NULL
            RETURN p.name, p.position, p.combine_forty, p.combine_vertical, p.athletic_score
            ORDER BY p.athletic_score DESC
            LIMIT 20
            ```

            **Contract Leaders:**
            ```cypher
            MATCH (p:Player)
            WHERE p.contract_apy IS NOT NULL
            RETURN p.name, p.position, p.contract_apy, p.contract_guaranteed, p.ktc_value
            ORDER BY p.contract_apy DESC
            LIMIT 20
            ```
            """)

    render_thoth_footer()


if __name__ == "__main__":
    main()
