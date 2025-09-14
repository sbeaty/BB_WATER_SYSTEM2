#!/usr/bin/env python3
"""
Test Delta Calculation Logic
Tests the updated delta calculation with counter reset handling
"""

from datetime import datetime, timedelta
from sql_historian_client import SQLHistorianClient, HistorianConfig
from shift_calculator import ShiftCalculator

def test_delta_calculation_scenarios():
    """Test various delta calculation scenarios including counter resets."""
    print("=" * 70)
    print("TESTING DELTA CALCULATION WITH COUNTER RESET HANDLING")
    print("=" * 70)
    
    client = SQLHistorianClient()
    
    # Test scenarios
    test_cases = [
        # (start_value, end_value, expected_result, description)
        (1000.0, 1500.0, 500.0, "Normal increment - no reset"),
        (500000.0, 600000.0, 100000.0, "Large normal increment"),
        (300000000.0, 500000.0, 500000.0, "Counter reset - end value is usage"),
        (4000000000.0, 1000000.0, 1295967295.0, "Counter rollover near 32-bit limit"),
        (0.0, 5000.0, 5000.0, "Starting from zero"),
        (5000.0, 0.0, 0.0, "Reset to zero - no usage"),
        (-100.0, 500.0, 500.0, "Invalid start value"),
        (1000.0, -50.0, 0.0, "Invalid end value"),
    ]
    
    print("Testing counter reset handling logic:")
    print("-" * 70)
    
    for i, (start_val, end_val, expected, description) in enumerate(test_cases, 1):
        print(f"Test {i}: {description}")
        print(f"  Start: {start_val:,.1f}, End: {end_val:,.1f}")
        
        # Test the calculation
        result = client._calculate_delta_with_reset_handling(start_val, end_val, "FT5101_Test")
        
        print(f"  Calculated: {result:,.1f}")
        print(f"  Expected: {expected:,.1f}")
        
        if abs(result - expected) < 0.1:  # Allow small floating point differences
            print("  [PASS] OK")
        else:
            print("  [FAIL] ERROR")
        print()

def test_real_tags_with_fixed_logic():
    """Test real tags with the updated calculation logic."""
    print("=" * 70)
    print("TESTING REAL TAGS WITH FIXED DELTA CALCULATION")
    print("=" * 70)
    
    # Tag mappings for testing
    test_tags = {
        'FT5101_TotalLts': 'WRP26_FT5101_Total',
        'FT5201_TotalLts': 'WRP26_FT5201_Total',
        'FT5301_TotalLts': 'WRP26_FT5301_Total', 
        'FT5402_TotalLts': 'WRP26_FT5402_Total',
        'FT2102_Usage_NonErasable': 'WRTC_FT2102_Total',
        'FT2201_Usage_NonErasable': 'WRTC_FT2201_Total',
    }
    
    historian_config = HistorianConfig()
    shift_calc = ShiftCalculator()
    
    try:
        with SQLHistorianClient(historian_config) as historian:
            # Get current shift times
            current_shift = shift_calc.get_current_shift_info()
            day_start, day_end = shift_calc.get_current_day_times()
            
            print(f"Current Shift: {current_shift['shift_name']}")
            print(f"Shift Period: {current_shift['start_time'].strftime('%H:%M')} - {current_shift['end_time'].strftime('%H:%M')}")
            print(f"24-Hour Period: {day_start.strftime('%d/%m %H:%M')} - {day_end.strftime('%d/%m %H:%M')}")
            print()
            
            for configured_tag, actual_tag in test_tags.items():
                print(f"Testing: {configured_tag} -> {actual_tag}")
                
                try:
                    # Test shift calculation
                    shift_result = historian.get_tag_delta(actual_tag, current_shift['start_time'], current_shift['end_time'])
                    
                    print(f"  Shift Calculation:")
                    print(f"    Start Value: {shift_result['start_value']:,.1f}" if shift_result['start_value'] else "    Start Value: No data")
                    print(f"    End Value: {shift_result['end_value']:,.1f}" if shift_result['end_value'] else "    End Value: No data")
                    print(f"    Delta: {shift_result['delta']:,.1f}")
                    print(f"    Method: {shift_result['calculation_method']}")
                    print(f"    Quality: {shift_result['data_quality']}")
                    
                    # Test day calculation
                    day_result = historian.get_tag_delta(actual_tag, day_start, day_end)
                    
                    print(f"  Day Calculation:")
                    print(f"    Start Value: {day_result['start_value']:,.1f}" if day_result['start_value'] else "    Start Value: No data")
                    print(f"    End Value: {day_result['end_value']:,.1f}" if day_result['end_value'] else "    End Value: No data")
                    print(f"    Delta: {day_result['delta']:,.1f}")
                    print(f"    Method: {day_result['calculation_method']}")
                    print(f"    Quality: {day_result['data_quality']}")
                    
                    # Validation checks
                    issues = []
                    if shift_result['delta'] < 0:
                        issues.append("Negative shift delta")
                    if day_result['delta'] < 0:
                        issues.append("Negative day delta")
                    if shift_result['delta'] > 50000:  # Reasonable limit for most equipment per shift
                        issues.append(f"Very high shift usage: {shift_result['delta']:,.1f}")
                    if day_result['delta'] > 150000:  # Reasonable limit for most equipment per day
                        issues.append(f"Very high day usage: {day_result['delta']:,.1f}")
                    
                    if issues:
                        print(f"  [WARNING] Issues detected:")
                        for issue in issues:
                            print(f"    - {issue}")
                    else:
                        print(f"  [OK] Calculations look reasonable")
                        
                except Exception as e:
                    print(f"  [ERROR] {str(e)}")
                
                print()
                
    except Exception as e:
        print(f"[ERROR] Failed to test real tags: {e}")

def main():
    """Main testing function."""
    print("Delta Calculation Testing Suite")
    print("Testing updated logic to handle counter resets properly")
    print()
    
    # Test the calculation logic with various scenarios
    test_delta_calculation_scenarios()
    
    # Test with real database tags
    test_real_tags_with_fixed_logic()
    
    print("=" * 70)
    print("TESTING COMPLETE")
    print("=" * 70)
    print()
    print("Key improvements in new calculation logic:")
    print("• Detects counter resets (when end_value < start_value)")
    print("• Handles counter rollovers for 32-bit totalizers") 
    print("• Uses end_value as usage when counter resets to zero")
    print("• Applies sanity checks to prevent extreme values")
    print("• Always returns positive usage values")

if __name__ == "__main__":
    main()