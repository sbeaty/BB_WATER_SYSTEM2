from datetime import datetime, time, timedelta
from typing import Tuple, Dict
import pytz

class ShiftCalculator:
    """Calculate shift times and periods for the water monitoring system."""
    
    # Shift definitions: (start_hour, shift_name)
    SHIFTS = [
        (7, "Day Shift"),      # 7:00 AM - 3:00 PM
        (15, "Afternoon Shift"), # 3:00 PM - 11:00 PM  
        (23, "Night Shift")    # 11:00 PM - 7:00 AM
    ]
    
    def __init__(self, timezone_str='Pacific/Auckland'):
        self.timezone = pytz.timezone(timezone_str)
        
    def get_current_shift_info(self) -> Dict:
        """Get information about the current shift."""
        now = datetime.now(self.timezone)
        current_hour = now.hour
        
        # Determine current shift
        if 7 <= current_hour < 15:
            shift_name = "Day Shift"
            shift_start_hour = 7
        elif 15 <= current_hour < 23:
            shift_name = "Afternoon Shift" 
            shift_start_hour = 15
        else:  # 23:00-6:59 (night shift spans midnight)
            shift_name = "Night Shift"
            shift_start_hour = 23
            
        start_time, end_time = self.get_shift_times(now, shift_start_hour)
        
        return {
            'shift_name': shift_name,
            'start_time': start_time,
            'end_time': end_time,
            'current_time': now
        }
        
    def get_shift_times(self, reference_time: datetime, shift_start_hour: int) -> Tuple[datetime, datetime]:
        """Calculate start and end times for a shift given a reference time and shift start hour."""
        ref_date = reference_time.date()
        
        if shift_start_hour == 23:  # Night shift spans midnight
            if reference_time.hour >= 23:
                # Current day 23:00 to next day 07:00
                start_time = datetime.combine(ref_date, time(23, 0))
                end_time = datetime.combine(ref_date + timedelta(days=1), time(7, 0))
            else:
                # Previous day 23:00 to current day 07:00
                start_time = datetime.combine(ref_date - timedelta(days=1), time(23, 0))
                end_time = datetime.combine(ref_date, time(7, 0))
        else:
            # Day and afternoon shifts (same day)
            start_time = datetime.combine(ref_date, time(shift_start_hour, 0))
            end_time = start_time + timedelta(hours=8)
            
        # Convert to timezone-aware datetime objects
        start_time = self.timezone.localize(start_time)
        end_time = self.timezone.localize(end_time)
        
        return start_time, end_time
        
    def get_current_day_times(self) -> Tuple[datetime, datetime]:
        """Get start and end times for the current 24-hour period (7 AM to 7 AM next day)."""
        now = datetime.now(self.timezone)
        current_date = now.date()
        
        if now.hour < 7:
            # Before 7 AM, so we want yesterday 7 AM to today 7 AM
            start_time = datetime.combine(current_date - timedelta(days=1), time(7, 0))
            end_time = datetime.combine(current_date, time(7, 0))
        else:
            # After 7 AM, so we want today 7 AM to tomorrow 7 AM
            start_time = datetime.combine(current_date, time(7, 0))
            end_time = datetime.combine(current_date + timedelta(days=1), time(7, 0))
            
        # Convert to timezone-aware datetime objects
        start_time = self.timezone.localize(start_time)
        end_time = self.timezone.localize(end_time)
        
        return start_time, end_time
        
    def get_previous_shift_times(self) -> Tuple[datetime, datetime]:
        """Get start and end times for the previous shift."""
        current_shift = self.get_current_shift_info()
        
        # Find previous shift
        if current_shift['shift_name'] == "Day Shift":
            # Previous was night shift (yesterday 23:00 to today 07:00)
            prev_start_hour = 23
            ref_time = current_shift['start_time'] - timedelta(hours=1)  # Go back to night shift
        elif current_shift['shift_name'] == "Afternoon Shift":
            # Previous was day shift (same day 07:00 to 15:00)
            prev_start_hour = 7
            ref_time = current_shift['start_time'] - timedelta(hours=1)  # Go back to day shift
        else:  # Night shift
            # Previous was afternoon shift (same day 15:00 to 23:00)
            prev_start_hour = 15
            ref_time = current_shift['start_time'] - timedelta(hours=1)  # Go back to afternoon shift
            
        return self.get_shift_times(ref_time, prev_start_hour)
        
    def get_all_shifts_today(self) -> list:
        """Get all three shift periods for the current day."""
        now = datetime.now(self.timezone)
        shifts = []
        
        for start_hour, shift_name in self.SHIFTS:
            start_time, end_time = self.get_shift_times(now, start_hour)
            shifts.append({
                'name': shift_name,
                'start_time': start_time,
                'end_time': end_time,
                'start_hour': start_hour
            })
            
        return shifts
        
    def format_shift_time_range(self, start_time: datetime, end_time: datetime) -> str:
        """Format shift time range as a readable string."""
        if start_time.date() != end_time.date():
            # Spans multiple days
            return f"{start_time.strftime('%Y-%m-%d %H:%M')} - {end_time.strftime('%Y-%m-%d %H:%M')}"
        else:
            # Same day
            return f"{start_time.strftime('%Y-%m-%d %H:%M')} - {end_time.strftime('%H:%M')}"

if __name__ == "__main__":
    # Test the shift calculator
    calc = ShiftCalculator()
    
    print("=== Shift Calculator Test ===")
    
    # Current shift info
    current = calc.get_current_shift_info()
    print(f"\nCurrent Shift: {current['shift_name']}")
    print(f"Time Range: {calc.format_shift_time_range(current['start_time'], current['end_time'])}")
    print(f"Current Time: {current['current_time'].strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Current day times (24-hour period)
    day_start, day_end = calc.get_current_day_times()
    print(f"\nCurrent 24-Hour Period:")
    print(f"Time Range: {calc.format_shift_time_range(day_start, day_end)}")
    
    # Previous shift
    prev_start, prev_end = calc.get_previous_shift_times()
    print(f"\nPrevious Shift:")
    print(f"Time Range: {calc.format_shift_time_range(prev_start, prev_end)}")
    
    # All shifts today
    print(f"\nAll Shifts Today:")
    for shift in calc.get_all_shifts_today():
        print(f"  {shift['name']}: {calc.format_shift_time_range(shift['start_time'], shift['end_time'])}")