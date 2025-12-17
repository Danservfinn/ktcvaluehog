"""Data loaders for NFLverse, Sleeper, and KTC."""
from .nflverse_loader import NFLverseLoader
from .id_resolver import IDResolver, UnifiedIDResolver
from .ktc_loader import KTCLoader
from .ktc_devy_loader import KTCDevyLoader
from .college_to_neo4j import CollegeToNeo4jETL

# 2025 Season loaders (require nflreadpy)
try:
    from .nfl2025_loader import NFL2025Loader, NFLREADPY_AVAILABLE
    from .nfl2025_to_neo4j import NFL2025ToNeo4jETL
except ImportError:
    NFL2025Loader = None
    NFL2025ToNeo4jETL = None
    NFLREADPY_AVAILABLE = False
