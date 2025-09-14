#!/usr/bin/env python3
"""
Tag Name Discovery Script
Finds the correct tag names in the historian database that match our configuration
"""

from sql_historian_client import SQLHistorianClient, HistorianConfig
from database import DatabaseManager, Threshold
import re

def find_matching_tags():
    """Find correct tag names in the historian database."""
    print("=" * 70)
    print("TAG NAME DISCOVERY & MAPPING")
    print("=" * 70)
    
    # Get configured thresholds
    db_manager = DatabaseManager()
    session = db_manager.get_session()
    
    try:
        thresholds = session.query(Threshold).all()
        configured_tags = set()
        for threshold in thresholds:
            tag_name = threshold.threshold_ref.replace('_day', '').replace('_shift', '')
            configured_tags.add(tag_name)
        
        print(f"Found {len(configured_tags)} unique configured tag names:")
        for tag in sorted(configured_tags):
            print(f"  - {tag}")
        print()
        
    finally:
        session.close()
    
    # Search for matching tags in historian
    config = HistorianConfig()
    
    try:
        with SQLHistorianClient(config) as historian:
            cursor = historian.connection.cursor()
            
            # Get all available tag names with recent data
            print("Searching historian database for matching tags...")
            print("-" * 70)
            
            tag_mappings = {}
            
            for configured_tag in sorted(configured_tags):
                print(f"\nSearching for: {configured_tag}")
                
                # Try different search patterns
                search_patterns = [
                    configured_tag,                    # Exact match
                    f"WRTC_{configured_tag}",         # With WRTC prefix
                    f"%{configured_tag}%",            # Contains pattern
                    f"WRTC_%{configured_tag.split('_')[0]}%", # Partial match with prefix
                ]
                
                found_tags = []
                
                for pattern in search_patterns:
                    try:
                        if '%' in pattern:
                            cursor.execute("""
                                SELECT DISTINCT TOP 10 TagName
                                FROM History
                                WHERE TagName LIKE ?
                                ORDER BY TagName
                            """, pattern)
                        else:
                            cursor.execute("""
                                SELECT DISTINCT TOP 5 TagName
                                FROM History
                                WHERE TagName = ?
                            """, pattern)
                        
                        results = cursor.fetchall()
                        for row in results:
                            tag_name = row[0]
                            if tag_name not in [t[0] for t in found_tags]:
                                # Get latest data for this tag
                                cursor.execute("""
                                    SELECT TOP 1 DateTime, Value
                                    FROM History
                                    WHERE TagName = ?
                                    ORDER BY DateTime DESC
                                """, tag_name)
                                
                                latest = cursor.fetchone()
                                if latest:
                                    found_tags.append((tag_name, latest[0], latest[1]))
                                    
                    except Exception as e:
                        continue  # Skip failed patterns
                
                if found_tags:
                    print(f"  Found {len(found_tags)} matching tags:")
                    for tag_name, timestamp, value in found_tags[:5]:  # Show top 5
                        print(f"    [OK] {tag_name}")
                        print(f"      Latest: {value} at {timestamp}")
                    
                    # Store best match (usually the first exact or closest match)
                    tag_mappings[configured_tag] = found_tags[0][0]
                else:
                    print(f"  [NOT FOUND] No matching tags found")
                    
                    # Try broader search for debugging
                    base_name = configured_tag.split('_')[0]  # e.g., "FT5101" from "FT5101_TotalLts"
                    try:
                        cursor.execute("""
                            SELECT DISTINCT TOP 5 TagName
                            FROM History
                            WHERE TagName LIKE ?
                            ORDER BY TagName
                        """, f"%{base_name}%")
                        
                        broad_results = cursor.fetchall()
                        if broad_results:
                            print(f"    Similar tags found with '{base_name}':")
                            for row in broad_results:
                                print(f"      ~ {row[0]}")
                    except:
                        pass
            
            # Summary of mappings
            print("\n" + "=" * 70)
            print("SUGGESTED TAG MAPPINGS")
            print("=" * 70)
            
            if tag_mappings:
                print(f"Found mappings for {len(tag_mappings)} out of {len(configured_tags)} configured tags:")
                print()
                for configured, actual in tag_mappings.items():
                    print(f"{configured:30} -> {actual}")
                
                # Generate updated CSV
                print(f"\n" + "-" * 70)
                print("RECOMMENDATIONS:")
                print("-" * 70)
                print("1. Update your threshold CSV file with the correct tag names:")
                print("   - Replace configured tag names with actual database tag names")
                print("   - The system appears to use 'WRTC_' prefix for many tags")
                print("   - Some tags may have different suffixes (_Value vs _Total vs _TotalLts)")
                
                print(f"\n2. Tags that need attention:")
                missing_tags = configured_tags - set(tag_mappings.keys())
                if missing_tags:
                    for tag in missing_tags:
                        print(f"   [MISSING] {tag} - No match found in database")
                else:
                    print("   [SUCCESS] All configured tags have potential matches!")
                    
            else:
                print("[FAILED] No tag mappings found!")
                print("\nPossible issues:")
                print("- Tag names in CSV don't match database tag names")
                print("- Tags may not be actively logging data")
                print("- Database may use different naming convention")
                
                # Show sample of available tags for reference
                print(f"\nSample of available tags in database:")
                cursor.execute("""
                    SELECT DISTINCT TOP 20 TagName
                    FROM History
                    WHERE TagName LIKE 'WRTC_%'
                    ORDER BY TagName
                """)
                sample_tags = cursor.fetchall()
                for row in sample_tags:
                    print(f"  {row[0]}")
                    
    except Exception as e:
        print(f"[ERROR] Error during tag discovery: {e}")
        return False
        
    print("\n" + "=" * 70)
    print("TAG DISCOVERY COMPLETE")
    print("=" * 70)
    return True

if __name__ == "__main__":
    find_matching_tags()