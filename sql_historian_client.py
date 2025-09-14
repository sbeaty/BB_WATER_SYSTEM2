try:
    import pyodbc
    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False
    pyodbc = None

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

try:
    from tag_mapping import get_database_tag_name
except ImportError:
    # If tag_mapping not available, create a simple fallback
    def get_database_tag_name(tag_name):
        return tag_name

@dataclass
class HistorianConfig:
    server: str = "192.168.10.236"
    database: str = "Runtime"
    username: str = "wwUser"
    password: str = "wwUser"
    driver: str = "ODBC Driver 17 for SQL Server"

class SQLHistorianClient:
    """Client to retrieve historical data from WonderWare Historian SQL Server database."""
    
    def __init__(self, config: HistorianConfig = None):
        self.config = config or HistorianConfig()
        self.connection = None
        
    def connect(self):
        """Establish connection to SQL Server."""
        if not PYODBC_AVAILABLE:
            print("ERROR: pyodbc not available. Install with: pip install pyodbc")
            return False
            
        try:
            connection_string = (
                f"DRIVER={{{self.config.driver}}};"
                f"SERVER={self.config.server};"
                f"DATABASE={self.config.database};"
                f"UID={self.config.username};"
                f"PWD={self.config.password};"
                f"TrustServerCertificate=yes;"
                f"CONNECTION_TIMEOUT=10;"
                f"QUERY_TIMEOUT=15;"
            )
            self.connection = pyodbc.connect(connection_string, timeout=10)
            return True
        except Exception as e:
            print(f"Failed to connect to SQL Server: {e}")
            return False
            
    def disconnect(self):
        """Close SQL Server connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
            
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        
    def get_tag_current_value(self, tag_name: str) -> Dict[str, Any]:
        """
        Get the most recent value for a single tag.
        
        Args:
            tag_name: Name of the tag to retrieve
            
        Returns:
            Dictionary with tag value information or error
        """
        if not self.connection:
            return {'value': None, 'error': 'No database connection'}
            
        try:
            # Get the latest value for the tag (look back 24 hours)
            query = """
            SET NOCOUNT ON
            DECLARE @StartDate DateTime
            DECLARE @EndDate DateTime
            SET @StartDate = DateAdd(hour,-24,GetDate())
            SET @EndDate = GetDate()
            SET NOCOUNT OFF
            
            SELECT TOP 1 
                temp.TagName,
                DateTime,
                Value,
                vValue,
                Unit = ISNULL(CAST(EngineeringUnit.Unit as NVARCHAR(20)),'N/A'),
                wwResolution,
                StartDateTime 
            FROM (
                SELECT * 
                FROM History
                WHERE History.TagName = ?
                AND wwRetrievalMode = 'Cyclic'
                AND wwCycleCount = 1
                AND wwVersion = 'Latest'
                AND DateTime >= @StartDate
                AND DateTime <= @EndDate
            ) temp
            LEFT JOIN AnalogTag ON AnalogTag.TagName = temp.TagName
            LEFT JOIN EngineeringUnit ON AnalogTag.EUKey = EngineeringUnit.EUKey
            WHERE temp.StartDateTime >= @StartDate
            ORDER BY DateTime DESC
            """
            
            cursor = self.connection.cursor()
            cursor.execute(query, tag_name)
            row = cursor.fetchone()
            
            if row:
                return {
                    'value': float(row.Value) if row.Value is not None else None,
                    'error': None,
                    'timestamp': row.DateTime,
                    'unit': row.Unit,
                    'tag_name': row.TagName
                }
            else:
                return {
                    'value': None, 
                    'error': f'No recent data found for tag {tag_name}'
                }
                
        except Exception as e:
            return {
                'value': None, 
                'error': f'Error retrieving tag {tag_name}: {str(e)}'
            }
    
    def get_tag_delta(self, tag_name: str, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """
        Calculate delta (difference) for a tag between start and end times.
        Handles totalizer counter resets/rollovers properly.
        
        Args:
            tag_name: Name of the tag
            start_time: Start time for calculation
            end_time: End time for calculation
            
        Returns:
            Dictionary containing delta calculation results
        """
        try:
            if not self.connection:
                return {
                    'delta': 0,
                    'start_value': None,
                    'end_value': None,
                    'data_quality': 'No Connection',
                    'calculation_method': 'Failed - No database connection'
                }
                
            # Get start value (closest to start_time)
            start_query = """
            DECLARE @StartDate DateTime
            DECLARE @EndDate DateTime
            SET @StartDate = ?
            SET @EndDate = DATEADD(MINUTE, 30, @StartDate)
            SET NOCOUNT OFF
            
            SELECT TOP 1 
                DateTime,
                Value,
                vValue
            FROM History
            WHERE TagName = ?
            AND wwRetrievalMode = 'Cyclic'
            AND wwCycleCount = 1
            AND wwVersion = 'Latest'
            AND DateTime >= @StartDate
            AND DateTime <= @EndDate
            ORDER BY DateTime ASC
            """
            
            # Get end value (closest to end_time)  
            end_query = """
            DECLARE @StartDate DateTime
            DECLARE @EndDate DateTime
            SET @EndDate = ?
            SET @StartDate = DATEADD(MINUTE, -30, @EndDate)
            SET NOCOUNT OFF
            
            SELECT TOP 1 
                DateTime,
                Value,
                vValue
            FROM History
            WHERE TagName = ?
            AND wwRetrievalMode = 'Cyclic'
            AND wwCycleCount = 1
            AND wwVersion = 'Latest'
            AND DateTime >= @StartDate
            AND DateTime <= @EndDate
            ORDER BY DateTime DESC
            """
            
            cursor = self.connection.cursor()
            
            # Get start value
            cursor.execute(start_query, start_time, tag_name)
            start_row = cursor.fetchone()
            
            # Get end value
            cursor.execute(end_query, end_time, tag_name)
            end_row = cursor.fetchone()
            
            if not start_row and not end_row:
                return {
                    'delta': 0,
                    'start_value': None,
                    'end_value': None,
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'data_quality': 'No Data',
                    'calculation_method': 'No data points found'
                }
            
            # Handle cases where we have data at one end but not the other
            start_value = float(start_row.Value) if start_row and start_row.Value is not None else None
            end_value = float(end_row.Value) if end_row and end_row.Value is not None else None
            
            # If we only have one data point, we cannot calculate a meaningful delta
            if start_value is None and end_value is None:
                return {
                    'delta': 0,
                    'start_value': None,
                    'end_value': None,
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'data_quality': 'No Data',
                    'calculation_method': 'No valid data points'
                }
            
            # If we're missing the end value, try to get the most recent value
            if end_value is None:
                try:
                    current_result = self.get_tag_current_value(tag_name)
                    if current_result.get('value') is not None:
                        end_value = float(current_result['value'])
                    else:
                        # Cannot calculate delta without end value
                        return {
                            'delta': 0,
                            'start_value': start_value,
                            'end_value': None,
                            'start_time': start_time.isoformat(),
                            'end_time': end_time.isoformat(),
                            'data_quality': 'Incomplete Data',
                            'calculation_method': 'Missing end value'
                        }
                except:
                    pass
            
            # If we're missing the start value, cannot calculate meaningful delta
            if start_value is None:
                return {
                    'delta': 0,
                    'start_value': None,
                    'end_value': end_value,
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'data_quality': 'Incomplete Data',
                    'calculation_method': 'Missing start value'
                }
            
            # Calculate delta with counter reset/rollover handling
            delta = self._calculate_delta_with_reset_handling(start_value, end_value, tag_name)
            
            return {
                'delta': delta,
                'start_value': start_value,
                'end_value': end_value,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'data_quality': 'Good',
                'calculation_method': 'SQL Server Historian Delta (with reset handling)'
            }
            
        except Exception as e:
            return {
                'delta': 0,
                'start_value': None,
                'end_value': None,
                'start_time': start_time.isoformat() if start_time else None,
                'end_time': end_time.isoformat() if end_time else None,
                'data_quality': 'Error',
                'calculation_method': f'Error: {str(e)}'
            }
    
    def _calculate_delta_with_reset_handling(self, start_value: float, end_value: float, tag_name: str) -> float:
        """
        Calculate delta between start and end values with proper handling of counter resets.
        
        Totalizer counters in industrial systems often reset to zero due to:
        - Counter overflow (reaching maximum value)
        - System restarts/maintenance
        - Equipment power cycles
        
        Args:
            start_value: Value at start time
            end_value: Value at end time
            tag_name: Tag name for logging/debugging
            
        Returns:
            Calculated usage delta (always >= 0)
        """
        # Simple case: normal increment (end > start)
        if end_value >= start_value:
            return end_value - start_value
            
        # Counter reset detected (end < start)
        # This happens when totalizer resets to 0 during the measurement period
        
        # Define reasonable maximum counter values for different tag types
        max_counter_values = {
            # Flow totalizers - typically 32-bit unsigned integers
            'FT': 4294967295,      # 2^32 - 1
            'FM': 4294967295,      # 2^32 - 1
            # Smaller totalizers might use 24-bit or 16-bit
            'default': 16777215    # 2^24 - 1 (conservative default)
        }
        
        # Determine likely maximum counter value based on tag name
        max_value = max_counter_values['default']
        for prefix, max_val in max_counter_values.items():
            if tag_name.startswith(prefix):
                max_value = max_val
                break
                
        # Check if start value indicates counter was near overflow
        if start_value > (max_value * 0.8):  # More than 80% of maximum
            # Likely counter rollover scenario
            # Usage = (max_value - start_value) + end_value
            calculated_delta = (max_value - start_value) + end_value
            
            # Sanity check: rollover delta shouldn't be too large for typical usage periods
            max_reasonable_usage = max_value * 0.1  # 10% of counter range per period
            if calculated_delta <= max_reasonable_usage:
                return calculated_delta
                
        # Counter reset scenario (system restart, maintenance, etc.)
        # In this case, end_value represents the usage since reset
        # This is the most common scenario in industrial systems
        
        # Additional sanity checks
        if end_value < 0:
            return 0  # Invalid end value
            
        # For very large end values after reset, apply reasonable limits
        # But be more lenient as these are totalizer readings, not hourly usage
        max_reasonable_totalizer = {
            'WRP26_FT5101': 50000,    # PC Barrel Washer - higher limit
            'WRP26_FT5201': 10000,    # Peelers  
            'WRP26_FT5301': 75000,    # Slicers - higher limit
            'WRP26_FT5402': 200000,   # Speed-Wash & ROCD - highest usage
            'WRTC_FT': 500000,        # General WRTC tags - industrial scale
            'WREP_FM': 100000,        # Flow meters
            'WRCKNEW_FT': 50000,      # Cooking area tags
            'default': 1000000        # Very conservative default - 1M units
        }
        
        # Find applicable limit based on full tag name first, then prefixes
        usage_limit = max_reasonable_totalizer['default']
        
        # Check for specific tag matches first
        for tag_pattern, limit in max_reasonable_totalizer.items():
            if tag_name.startswith(tag_pattern):
                usage_limit = limit
                break
                
        # Only cap extremely large values that are clearly data errors
        # Allow up to 10x the expected limit to handle unusual but valid conditions
        extreme_limit = usage_limit * 10
        if end_value > extreme_limit:
            print(f"Warning: Extremely large totalizer value for {tag_name}: {end_value:,.0f}. Capping to {extreme_limit:,.0f}")
            return extreme_limit
            
        # Return end_value as the usage since counter reset
        return end_value
            
    def get_multiple_tags_current_values(self, tag_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get current values for multiple tags.
        
        Args:
            tag_names: List of tag names to retrieve
            
        Returns:
            Dictionary mapping tag names to their value information
        """
        results = {}
        for tag_name in tag_names:
            results[tag_name] = self.get_tag_current_value(tag_name)
        return results
    
    def get_multiple_tags_batch(self, tag_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get current values for multiple tags in a single batch query.
        Much faster than individual queries.
        
        Args:
            tag_names: List of tag names to retrieve
            
        Returns:
            Dictionary mapping tag names to their value information
        """
        if not tag_names:
            return {}
            
        if not self.connection:
            return {}
        
        try:
            cursor = self.connection.cursor()
            
            # Create placeholders for IN clause
            placeholders = ','.join(['?' for _ in tag_names])
            
            query = f"""
            SELECT 
                h.wwTagName,
                h.wwValue,
                h.wwTimeStamp,
                h.wwQualityRule
            FROM History h
            INNER JOIN (
                SELECT wwTagName, MAX(wwTimeStamp) as MaxTime
                FROM History 
                WHERE wwTagName IN ({placeholders})
                AND wwTimeStamp >= ?
                GROUP BY wwTagName
            ) latest ON h.wwTagName = latest.wwTagName AND h.wwTimeStamp = latest.MaxTime
            """
            
            # Execute with tag names and recent time filter (last hour)
            recent_time = datetime.now() - timedelta(hours=1)
            params = tag_names + [recent_time]
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # Process results
            results = {}
            for row in rows:
                tag_name = row[0]
                results[tag_name] = {
                    'tag_name': tag_name,
                    'value': float(row[1]) if row[1] is not None else None,
                    'timestamp': row[2],
                    'quality': row[3],
                    'success': True
                }
            
            # Add missing tags with no data
            for tag_name in tag_names:
                if tag_name not in results:
                    results[tag_name] = {
                        'tag_name': tag_name,
                        'value': None,
                        'timestamp': None,
                        'quality': None,
                        'success': False,
                        'error': 'No recent data found'
                    }
            
            return results
            
        except Exception as e:
            print(f"Error in batch query for tags {tag_names}: {e}")
            # Fallback to individual queries
            return self.get_multiple_tags_current_values(tag_names)
        
    def get_tag_historical_data(self, tag_name: str, start_time: datetime, end_time: datetime, 
                               max_points: int = 100) -> List[Dict[str, Any]]:
        """
        Get historical data for a tag within a time range.
        
        Args:
            tag_name: Name of the tag
            start_time: Start of time range
            end_time: End of time range
            max_points: Maximum number of data points to return
            
        Returns:
            List of dictionaries with timestamp and value data
        """
        if not self.connection:
            return []
            
        try:
            query = """
            SET NOCOUNT ON
            DECLARE @StartDate DateTime
            DECLARE @EndDate DateTime
            SET @StartDate = ?
            SET @EndDate = ?
            SET NOCOUNT OFF
            
            SELECT 
                temp.TagName,
                DateTime,
                Value,
                vValue,
                Unit = ISNULL(CAST(EngineeringUnit.Unit as NVARCHAR(20)),'N/A'),
                wwResolution,
                StartDateTime 
            FROM (
                SELECT * 
                FROM History
                WHERE History.TagName = ?
                AND wwRetrievalMode = 'Cyclic'
                AND wwCycleCount = ?
                AND wwVersion = 'Latest'
                AND DateTime >= @StartDate
                AND DateTime <= @EndDate
            ) temp
            LEFT JOIN AnalogTag ON AnalogTag.TagName = temp.TagName
            LEFT JOIN EngineeringUnit ON AnalogTag.EUKey = EngineeringUnit.EUKey
            WHERE temp.StartDateTime >= @StartDate
            ORDER BY DateTime ASC
            """
            
            cursor = self.connection.cursor()
            cursor.execute(query, start_time, end_time, tag_name, max_points)
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                results.append({
                    'timestamp': row.DateTime,
                    'value': float(row.Value) if row.Value is not None else None,
                    'unit': row.Unit,
                    'tag_name': row.TagName
                })
                
            return results
            
        except Exception as e:
            print(f"Error retrieving historical data for {tag_name}: {e}")
            return []
            
    def test_connection(self) -> bool:
        """Test the database connection."""
        try:
            with self:
                cursor = self.connection.cursor()
                cursor.execute("SELECT 1")
                return True
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False


if __name__ == "__main__":
    # Test the historian client
    print("Testing SQL Historian Client...")
    
    historian = SQLHistorianClient()
    
    if historian.test_connection():
        print("✅ Database connection successful!")
        
        # Test getting current value for a tag
        with historian:
            test_tag = "FT5201_TotalLts"
            result = historian.get_tag_current_value(test_tag)
            print(f"Current value for {test_tag}: {result}")
            
            # Test historical data
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=1)
            historical = historian.get_tag_historical_data(test_tag, start_time, end_time, 10)
            print(f"Historical data points: {len(historical)}")
            for point in historical[:3]:  # Show first 3 points
                print(f"  {point['timestamp']}: {point['value']} {point['unit']}")
    else:
        print("❌ Database connection failed!")