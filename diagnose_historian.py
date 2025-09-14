#!/usr/bin/env python3
"""
Historian Database Diagnostic Script
Investigates the actual structure and available tags in the historian database
"""

from sql_historian_client import SQLHistorianClient, HistorianConfig
from datetime import datetime, timedelta
import traceback

def diagnose_historian():
    """Run comprehensive historian database diagnostics."""
    print("=" * 60)
    print("HISTORIAN DATABASE DIAGNOSTICS")
    print("=" * 60)
    
    config = HistorianConfig()
    print(f"Testing connection to: {config.server}/{config.database}")
    print(f"Username: {config.username}")
    print()
    
    try:
        with SQLHistorianClient(config) as historian:
            
            # Test 1: Basic connection
            print("1. TESTING BASIC CONNECTION...")
            print("-" * 40)
            if historian.connection:
                print("[SUCCESS] Connected to SQL Server")
                cursor = historian.connection.cursor()
                cursor.execute("SELECT @@VERSION")
                version = cursor.fetchone()[0]
                version_line = version.split('\n')[0]
                print(f"SQL Server Version: {version_line}")
                print()
            else:
                print("[FAILED] Could not connect to SQL Server")
                return
                
            # Test 2: Check available tables
            print("2. CHECKING AVAILABLE TABLES...")
            print("-" * 40)
            cursor.execute("""
                SELECT TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
            """)
            tables = cursor.fetchall()
            print(f"Found {len(tables)} tables:")
            for table in tables[:10]:  # Show first 10 tables
                print(f"  - {table[0]}")
            if len(tables) > 10:
                print(f"  ... and {len(tables) - 10} more tables")
            print()
            
            # Test 3: Check History table structure
            print("3. ANALYZING HISTORY TABLE...")
            print("-" * 40)
            try:
                cursor.execute("""
                    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = 'History'
                    ORDER BY ORDINAL_POSITION
                """)
                columns = cursor.fetchall()
                if columns:
                    print("History table columns:")
                    for col in columns:
                        print(f"  - {col[0]} ({col[1]}) {'NULL' if col[2] == 'YES' else 'NOT NULL'}")
                else:
                    print("[WARNING] History table not found or no access")
                print()
            except Exception as e:
                print(f"[ERROR] Could not analyze History table: {e}")
                print()
                
            # Test 4: Check recent data availability
            print("4. CHECKING RECENT DATA AVAILABILITY...")
            print("-" * 40)
            try:
                # Check for any recent data in last 24 hours
                cursor.execute("""
                    SELECT COUNT(*) as total_records
                    FROM History
                    WHERE DateTime >= DATEADD(hour, -24, GETDATE())
                """)
                recent_count = cursor.fetchone()[0]
                print(f"Records in last 24 hours: {recent_count:,}")
                
                if recent_count > 0:
                    # Get date range of available data
                    cursor.execute("""
                        SELECT 
                            MIN(DateTime) as earliest,
                            MAX(DateTime) as latest
                        FROM History
                    """)
                    date_range = cursor.fetchone()
                    print(f"Data range: {date_range[0]} to {date_range[1]}")
                else:
                    print("[WARNING] No recent data found in History table")
                print()
            except Exception as e:
                print(f"[ERROR] Could not check data availability: {e}")
                print()
                
            # Test 5: Sample tag names
            print("5. DISCOVERING AVAILABLE TAG NAMES...")
            print("-" * 40)
            try:
                cursor.execute("""
                    SELECT TOP 20 DISTINCT TagName
                    FROM History
                    WHERE DateTime >= DATEADD(hour, -24, GETDATE())
                    ORDER BY TagName
                """)
                tags = cursor.fetchall()
                if tags:
                    print(f"Sample of {len(tags)} active tag names:")
                    for tag in tags:
                        print(f"  - {tag[0]}")
                else:
                    # Try without date filter
                    cursor.execute("""
                        SELECT TOP 20 DISTINCT TagName
                        FROM History
                        ORDER BY TagName
                    """)
                    all_tags = cursor.fetchall()
                    if all_tags:
                        print(f"Sample of {len(all_tags)} tag names (no recent data):")
                        for tag in all_tags:
                            print(f"  - {tag[0]}")
                    else:
                        print("[WARNING] No tag names found in History table")
                print()
            except Exception as e:
                print(f"[ERROR] Could not retrieve tag names: {e}")
                print()
                
            # Test 6: Check for our specific tags
            print("6. CHECKING FOR CONFIGURED TAG NAMES...")
            print("-" * 40)
            test_tags = [
                'FT5101_TotalLts', 
                'FT5201_TotalLts',
                'FT5301_TotalLts',
                'FT5402_TotalLts'
            ]
            
            for tag in test_tags:
                try:
                    cursor.execute("""
                        SELECT COUNT(*) as count,
                               MAX(DateTime) as latest
                        FROM History
                        WHERE TagName = ?
                    """, tag)
                    result = cursor.fetchone()
                    if result[0] > 0:
                        print(f"  [FOUND] {tag}: {result[0]:,} records, latest: {result[1]}")
                    else:
                        print(f"  [NOT FOUND] {tag}: No records")
                except Exception as e:
                    print(f"  [ERROR] {tag}: {e}")
            print()
            
            # Test 7: Check AnalogTag and EngineeringUnit tables
            print("7. CHECKING METADATA TABLES...")
            print("-" * 40)
            try:
                cursor.execute("SELECT COUNT(*) FROM AnalogTag")
                analog_count = cursor.fetchone()[0]
                print(f"AnalogTag records: {analog_count:,}")
                
                cursor.execute("SELECT COUNT(*) FROM EngineeringUnit")
                unit_count = cursor.fetchone()[0]
                print(f"EngineeringUnit records: {unit_count:,}")
                
                # Sample analog tags
                cursor.execute("""
                    SELECT TOP 10 TagName, Description
                    FROM AnalogTag
                    ORDER BY TagName
                """)
                analog_tags = cursor.fetchall()
                if analog_tags:
                    print("Sample analog tags:")
                    for tag in analog_tags:
                        desc = tag[1][:50] + "..." if tag[1] and len(tag[1]) > 50 else tag[1]
                        print(f"  - {tag[0]}: {desc}")
                print()
            except Exception as e:
                print(f"[ERROR] Could not check metadata tables: {e}")
                print()
                
            # Test 8: Alternative query approach
            print("8. TESTING ALTERNATIVE QUERY METHODS...")
            print("-" * 40)
            test_tag = 'FT5101_TotalLts'  # Try one of our configured tags
            
            # Try simple query without time constraints
            try:
                cursor.execute("""
                    SELECT TOP 5 TagName, DateTime, Value
                    FROM History
                    WHERE TagName LIKE ?
                    ORDER BY DateTime DESC
                """, f'%{test_tag}%')
                
                results = cursor.fetchall()
                if results:
                    print(f"Found {len(results)} records for pattern '%{test_tag}%':")
                    for row in results:
                        print(f"  {row[0]}: {row[2]} at {row[1]}")
                else:
                    print(f"No records found for pattern '%{test_tag}%'")
                    
                    # Try even broader search
                    cursor.execute("""
                        SELECT TOP 5 TagName, DateTime, Value
                        FROM History
                        WHERE TagName LIKE '%FT%'
                        ORDER BY DateTime DESC
                    """)
                    broad_results = cursor.fetchall()
                    if broad_results:
                        print(f"Found {len(broad_results)} records with 'FT' pattern:")
                        for row in broad_results:
                            print(f"  {row[0]}: {row[2]} at {row[1]}")
                    else:
                        print("No records found with 'FT' pattern")
                print()
            except Exception as e:
                print(f"[ERROR] Alternative query failed: {e}")
                print()
            
    except Exception as e:
        print(f"[CRITICAL ERROR] Diagnostic failed: {e}")
        traceback.print_exc()
        return False
        
    print("=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)
    return True

if __name__ == "__main__":
    diagnose_historian()