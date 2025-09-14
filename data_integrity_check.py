#!/usr/bin/env python3
"""
Data Integrity Check - Shift and 24-Hour Calculations vs Thresholds
Validates data accuracy, shift calculations, and threshold comparisons
"""

import sys
from datetime import datetime, timedelta
from database import DatabaseManager, Threshold
from sql_historian_client import SQLHistorianClient, HistorianConfig
from shift_calculator import ShiftCalculator
import traceback

class DataIntegrityChecker:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.shift_calc = ShiftCalculator()
        self.historian_config = HistorianConfig()
        self.results = {
            'total_checks': 0,
            'data_warnings': [],
            'calculation_errors': [],
            'threshold_violations': [],
            'data_quality_issues': [],
            'timing_issues': [],
            'summary': {}
        }
        
        # Tag mappings from validation results
        self.tag_mappings = {
            'FM8200_LitresTotal': 'WREP_FM8200_LitresTotal',
            'FT2102_Usage_NonErasable': 'WRTC_FT2102_Total',
            'FT2104_Usage_NonErasable': 'WRTC_FT2104_Total',
            'FT2201_Usage_NonErasable': 'WRTC_FT2201_Total',
            'FT2301_Usage2_NonErasable': 'WRTC_FT2301_Total',
            'FT2302_Usage2_NonErasable': 'WRTC_FT2302_Total',
            'FT3101_Totalizer1': 'WRCKNEW_FT3101_Totalizer1',
            'FT3104_Totalizer1': 'WRCKNEW_FT3104_Totalizer1',
            'FT3105_Totalizer1': 'WRCKNEW_FT3105_Totalizer1',
            'FT3106_Totalizer1': 'WRCKNEW_FT3106_Totalizer1',
            'FT5240_Total_m3': 'WRP26_FT5240_Total_m3',
            'FT5241_Total_m3': 'WRP26_FT5241_Total_m3',
            'FT5242_Total_m3': 'WRP26_FT5242_Total_m3',
            # Suggested corrections for missing tags
            'FT5101_TotalLts': 'WRP26_FT5101_Total',
            'FT5201_TotalLts': 'WRP26_FT5201_Total',
            'FT5301_TotalLts': 'WRP26_FT5301_Total',
            'FT5402_TotalLts': 'WRP26_FT5402_Total',
            'FM8201Total_Actual': 'WREP_FM8201Total',
            'FT3503_l1_Process_variables_Totalizer1': 'WRCKNEW_FT3503_Usage.NonErasable',
            'FT4101_l1_Process_variables_Totalizer1': 'WREP_FT4101_CW_Total',
            'HotWater_Total_lit': 'WRCKNEW_HotWaterRMF_Value'
        }
        
    def extract_tag_name(self, threshold_ref):
        """Extract the base tag name from threshold reference."""
        return threshold_ref.replace('_day', '').replace('_shift', '')
        
    def get_actual_tag_name(self, configured_tag):
        """Get the actual database tag name."""
        return self.tag_mappings.get(configured_tag, configured_tag)
        
    def check_data_availability(self, tag_name, time_range_hours=25):
        """Check if tag has sufficient data for calculations."""
        try:
            with SQLHistorianClient(self.historian_config) as historian:
                end_time = datetime.now()
                start_time = end_time - timedelta(hours=time_range_hours)
                
                # Get historical data points
                historical_data = historian.get_tag_historical_data(tag_name, start_time, end_time, 100)
                
                if not historical_data:
                    return {
                        'sufficient_data': False,
                        'data_points': 0,
                        'time_span_hours': 0,
                        'issue': 'No historical data available'
                    }
                
                # Calculate actual time span of data
                timestamps = [point['timestamp'] for point in historical_data if point['timestamp']]
                if not timestamps:
                    return {
                        'sufficient_data': False,
                        'data_points': len(historical_data),
                        'time_span_hours': 0,
                        'issue': 'No valid timestamps'
                    }
                
                time_span = max(timestamps) - min(timestamps)
                time_span_hours = time_span.total_seconds() / 3600
                
                # Check if we have enough data for reliable calculations
                sufficient_data = (
                    len(historical_data) >= 10 and  # At least 10 data points
                    time_span_hours >= 8  # At least 8 hours of data
                )
                
                return {
                    'sufficient_data': sufficient_data,
                    'data_points': len(historical_data),
                    'time_span_hours': time_span_hours,
                    'oldest_timestamp': min(timestamps),
                    'newest_timestamp': max(timestamps),
                    'issue': None if sufficient_data else 'Insufficient data for reliable calculations'
                }
                
        except Exception as e:
            return {
                'sufficient_data': False,
                'data_points': 0,
                'time_span_hours': 0,
                'issue': f'Error checking data availability: {str(e)}'
            }
            
    def validate_shift_calculation(self, tag_name, threshold):
        """Validate shift period calculation accuracy."""
        try:
            current_shift = self.shift_calc.get_current_shift_info()
            
            with SQLHistorianClient(self.historian_config) as historian:
                # Get shift delta calculation
                shift_result = historian.get_tag_delta(tag_name, current_shift['start_time'], current_shift['end_time'])
                
                # Validate calculation components
                validation = {
                    'tag_name': tag_name,
                    'threshold_ref': threshold.threshold_ref,
                    'shift_name': current_shift['shift_name'],
                    'start_time': current_shift['start_time'],
                    'end_time': current_shift['end_time'],
                    'calculated_delta': shift_result.get('delta', 0),
                    'start_value': shift_result.get('start_value'),
                    'end_value': shift_result.get('end_value'),
                    'data_quality': shift_result.get('data_quality', 'Unknown'),
                    'calculation_method': shift_result.get('calculation_method', 'Unknown'),
                    'issues': []
                }
                
                # Check for calculation issues
                if validation['data_quality'] != 'Good':
                    validation['issues'].append(f"Poor data quality: {validation['data_quality']}")
                    
                if validation['start_value'] is None or validation['end_value'] is None:
                    validation['issues'].append("Missing start or end values for delta calculation")
                    
                if validation['calculated_delta'] < 0:
                    validation['issues'].append(f"Negative delta detected: {validation['calculated_delta']}")
                    
                # Check if delta seems reasonable (basic sanity check)
                if validation['calculated_delta'] > threshold.limit_value * 10:  # More than 10x threshold
                    validation['issues'].append(f"Extremely high delta: {validation['calculated_delta']} (threshold: {threshold.limit_value})")
                    
                # Validate time period duration
                expected_duration = 8 * 3600  # 8 hours in seconds
                actual_duration = (current_shift['end_time'] - current_shift['start_time']).total_seconds()
                if abs(actual_duration - expected_duration) > 300:  # Allow 5 minutes tolerance
                    validation['issues'].append(f"Incorrect shift duration: {actual_duration/3600:.1f}h (expected: 8h)")
                
                return validation
                
        except Exception as e:
            return {
                'tag_name': tag_name,
                'threshold_ref': threshold.threshold_ref,
                'issues': [f'Error in shift calculation: {str(e)}']
            }
            
    def validate_day_calculation(self, tag_name, threshold):
        """Validate 24-hour period calculation accuracy."""
        try:
            day_start, day_end = self.shift_calc.get_current_day_times()
            
            with SQLHistorianClient(self.historian_config) as historian:
                # Get day delta calculation
                day_result = historian.get_tag_delta(tag_name, day_start, day_end)
                
                # Validate calculation components
                validation = {
                    'tag_name': tag_name,
                    'threshold_ref': threshold.threshold_ref,
                    'day_start': day_start,
                    'day_end': day_end,
                    'calculated_delta': day_result.get('delta', 0),
                    'start_value': day_result.get('start_value'),
                    'end_value': day_result.get('end_value'),
                    'data_quality': day_result.get('data_quality', 'Unknown'),
                    'calculation_method': day_result.get('calculation_method', 'Unknown'),
                    'issues': []
                }
                
                # Check for calculation issues
                if validation['data_quality'] != 'Good':
                    validation['issues'].append(f"Poor data quality: {validation['data_quality']}")
                    
                if validation['start_value'] is None or validation['end_value'] is None:
                    validation['issues'].append("Missing start or end values for delta calculation")
                    
                if validation['calculated_delta'] < 0:
                    validation['issues'].append(f"Negative delta detected: {validation['calculated_delta']}")
                    
                # Check if delta seems reasonable (basic sanity check)
                if validation['calculated_delta'] > threshold.limit_value * 5:  # More than 5x threshold
                    validation['issues'].append(f"Extremely high delta: {validation['calculated_delta']} (threshold: {threshold.limit_value})")
                    
                # Validate time period duration
                expected_duration = 24 * 3600  # 24 hours in seconds
                actual_duration = (day_end - day_start).total_seconds()
                if abs(actual_duration - expected_duration) > 300:  # Allow 5 minutes tolerance
                    validation['issues'].append(f"Incorrect day duration: {actual_duration/3600:.1f}h (expected: 24h)")
                
                return validation
                
        except Exception as e:
            return {
                'tag_name': tag_name,
                'threshold_ref': threshold.threshold_ref,
                'issues': [f'Error in day calculation: {str(e)}']
            }
            
    def check_threshold_logic(self, threshold, current_value, calculated_value):
        """Validate threshold comparison logic."""
        issues = []
        
        # Check threshold configuration
        if threshold.limit_value <= 0:
            issues.append(f"Invalid threshold limit: {threshold.limit_value}")
            
        if threshold.comparison_operator not in ['>=', '>', '<=', '<', '==', '!=']:
            issues.append(f"Invalid comparison operator: {threshold.comparison_operator}")
            
        # Validate target type logic
        if threshold.target == 'absolute_value' and current_value is None:
            issues.append("Absolute value target but no current value available")
            
        if threshold.target in ['shift_total', 'day_total'] and calculated_value is None:
            issues.append(f"{threshold.target} target but no calculated value available")
            
        # Check for threshold violations
        test_value = calculated_value if threshold.target in ['shift_total', 'day_total'] else current_value
        
        if test_value is not None:
            violation = False
            if threshold.comparison_operator == '>=':
                violation = test_value >= threshold.limit_value
            elif threshold.comparison_operator == '>':
                violation = test_value > threshold.limit_value
            elif threshold.comparison_operator == '<=':
                violation = test_value <= threshold.limit_value
            elif threshold.comparison_operator == '<':
                violation = test_value < threshold.limit_value
                
            if violation:
                issues.append(f"THRESHOLD VIOLATION: {test_value} {threshold.comparison_operator} {threshold.limit_value}")
        
        return issues
        
    def run_integrity_check(self):
        """Run comprehensive data integrity check."""
        print("=" * 80)
        print("WATER MONITORING SYSTEM - DATA INTEGRITY CHECK")
        print("=" * 80)
        print(f"Check started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Get all thresholds
        session = self.db_manager.get_session()
        
        try:
            thresholds = session.query(Threshold).filter_by(enabled=True).all()
            self.results['total_checks'] = len(thresholds)
            
            if not thresholds:
                print("[ERROR] No enabled thresholds found!")
                return
                
            print(f"Checking data integrity for {len(thresholds)} threshold configurations...")
            print("-" * 80)
            
            # Group thresholds by base tag for efficiency
            tag_groups = {}
            for threshold in thresholds:
                base_tag = self.extract_tag_name(threshold.threshold_ref)
                if base_tag not in tag_groups:
                    tag_groups[base_tag] = []
                tag_groups[base_tag].append(threshold)
            
            print(f"Processing {len(tag_groups)} unique tags...")
            print()
            
            # Process each tag group
            for i, (configured_tag, tag_thresholds) in enumerate(tag_groups.items(), 1):
                print(f"[{i:2d}/{len(tag_groups)}] Checking: {configured_tag}")
                
                actual_tag = self.get_actual_tag_name(configured_tag)
                if actual_tag != configured_tag:
                    print(f"    Using mapped tag: {actual_tag}")
                
                # Check data availability first
                data_check = self.check_data_availability(actual_tag)
                if not data_check['sufficient_data']:
                    warning = {
                        'type': 'DATA_AVAILABILITY',
                        'tag': configured_tag,
                        'actual_tag': actual_tag,
                        'issue': data_check['issue'],
                        'data_points': data_check['data_points'],
                        'time_span_hours': data_check['time_span_hours'],
                        'severity': 'HIGH' if data_check['data_points'] == 0 else 'MEDIUM'
                    }
                    self.results['data_quality_issues'].append(warning)
                    print(f"    [WARNING] {data_check['issue']}")
                    print(f"    Data points: {data_check['data_points']}, Time span: {data_check['time_span_hours']:.1f}h")
                
                # Process each threshold for this tag
                for threshold in tag_thresholds:
                    print(f"      Checking threshold: {threshold.threshold_ref}")
                    
                    # Get current value
                    try:
                        with SQLHistorianClient(self.historian_config) as historian:
                            current_result = historian.get_tag_current_value(actual_tag)
                            current_value = current_result.get('value')
                            
                            # Initialize calculated_value
                            calculated_value = None
                            
                            # Validate calculations based on target type
                            if threshold.target == 'shift_total':
                                validation = self.validate_shift_calculation(actual_tag, threshold)
                                calculated_value = validation.get('calculated_delta')
                                
                                if validation.get('issues'):
                                    self.results['calculation_errors'].append({
                                        'type': 'SHIFT_CALCULATION',
                                        'threshold_ref': threshold.threshold_ref,
                                        'tag': actual_tag,
                                        'issues': validation['issues'],
                                        'severity': 'HIGH'
                                    })
                                    for issue in validation['issues']:
                                        print(f"        [ERROR] Shift calc: {issue}")
                                        
                            elif threshold.target == 'day_total':
                                validation = self.validate_day_calculation(actual_tag, threshold)
                                calculated_value = validation.get('calculated_delta')
                                
                                if validation.get('issues'):
                                    self.results['calculation_errors'].append({
                                        'type': 'DAY_CALCULATION',
                                        'threshold_ref': threshold.threshold_ref,
                                        'tag': actual_tag,
                                        'issues': validation['issues'],
                                        'severity': 'HIGH'
                                    })
                                    for issue in validation['issues']:
                                        print(f"        [ERROR] Day calc: {issue}")
                                        
                            else:  # absolute_value
                                calculated_value = current_value
                            
                            # Check threshold logic
                            threshold_issues = self.check_threshold_logic(threshold, current_value, calculated_value)
                            if threshold_issues:
                                for issue in threshold_issues:
                                    if 'VIOLATION' in issue:
                                        self.results['threshold_violations'].append({
                                            'threshold_ref': threshold.threshold_ref,
                                            'tag': actual_tag,
                                            'issue': issue,
                                            'severity': threshold.severity.upper(),
                                            'current_value': current_value,
                                            'calculated_value': calculated_value,
                                            'limit': threshold.limit_value
                                        })
                                        print(f"        [VIOLATION] {issue}")
                                    else:
                                        self.results['data_warnings'].append({
                                            'threshold_ref': threshold.threshold_ref,
                                            'tag': actual_tag,
                                            'issue': issue,
                                            'severity': 'MEDIUM'
                                        })
                                        print(f"        [WARNING] {issue}")
                            else:
                                print(f"        [OK] Threshold check passed")
                                
                    except Exception as e:
                        error = {
                            'type': 'PROCESSING_ERROR',
                            'threshold_ref': threshold.threshold_ref,
                            'tag': actual_tag,
                            'error': str(e),
                            'severity': 'HIGH'
                        }
                        self.results['calculation_errors'].append(error)
                        print(f"        [ERROR] {str(e)}")
                
                print()
                
        except Exception as e:
            print(f"[CRITICAL ERROR] Integrity check failed: {e}")
            traceback.print_exc()
        finally:
            session.close()
            
        # Generate summary
        self.generate_summary_report()
        
    def generate_summary_report(self):
        """Generate comprehensive summary report."""
        print("=" * 80)
        print("DATA INTEGRITY SUMMARY REPORT")
        print("=" * 80)
        
        # Calculate summary statistics
        total_issues = (
            len(self.results['data_warnings']) +
            len(self.results['calculation_errors']) +
            len(self.results['threshold_violations']) +
            len(self.results['data_quality_issues'])
        )
        
        print(f"Total Configurations Checked: {self.results['total_checks']}")
        print(f"Total Issues Found: {total_issues}")
        print()
        
        # Data Quality Issues
        if self.results['data_quality_issues']:
            print(f"DATA QUALITY ISSUES ({len(self.results['data_quality_issues'])}):")
            print("-" * 50)
            for issue in self.results['data_quality_issues']:
                print(f"[{issue['severity']}] {issue['tag']}")
                print(f"  Issue: {issue['issue']}")
                print(f"  Data Points: {issue['data_points']}")
                print(f"  Time Span: {issue['time_span_hours']:.1f} hours")
                print()
        
        # Calculation Errors
        if self.results['calculation_errors']:
            print(f"CALCULATION ERRORS ({len(self.results['calculation_errors'])}):")
            print("-" * 50)
            for error in self.results['calculation_errors']:
                print(f"[{error['severity']}] {error['threshold_ref']}")
                print(f"  Tag: {error['tag']}")
                print(f"  Type: {error['type']}")
                for issue in error.get('issues', [error.get('error', 'Unknown error')]):
                    print(f"  - {issue}")
                print()
        
        # Threshold Violations
        if self.results['threshold_violations']:
            print(f"ACTIVE THRESHOLD VIOLATIONS ({len(self.results['threshold_violations'])}):")
            print("-" * 50)
            for violation in self.results['threshold_violations']:
                print(f"[{violation['severity']}] {violation['threshold_ref']}")
                print(f"  Tag: {violation['tag']}")
                print(f"  Current: {violation['current_value']}")
                print(f"  Calculated: {violation['calculated_value']}")
                print(f"  Limit: {violation['limit']}")
                print(f"  Issue: {violation['issue']}")
                print()
        
        # Data Warnings
        if self.results['data_warnings']:
            print(f"DATA WARNINGS ({len(self.results['data_warnings'])}):")
            print("-" * 50)
            for warning in self.results['data_warnings']:
                print(f"[{warning['severity']}] {warning['threshold_ref']}")
                print(f"  Tag: {warning['tag']}")
                print(f"  Issue: {warning['issue']}")
                print()
        
        # Recommendations
        print("RECOMMENDATIONS:")
        print("-" * 50)
        
        if self.results['data_quality_issues']:
            print("1. DATA QUALITY IMPROVEMENTS:")
            high_priority_tags = [issue['tag'] for issue in self.results['data_quality_issues'] if issue['severity'] == 'HIGH']
            if high_priority_tags:
                print("   HIGH PRIORITY - Fix these tags immediately:")
                for tag in set(high_priority_tags):
                    print(f"   - {tag}")
                    
        if self.results['calculation_errors']:
            print("2. CALCULATION FIXES NEEDED:")
            print("   - Review shift and day calculation logic")
            print("   - Verify time zone settings")
            print("   - Check data historian query parameters")
            
        if self.results['threshold_violations']:
            print("3. IMMEDIATE ATTENTION REQUIRED:")
            critical_violations = [v for v in self.results['threshold_violations'] if v['severity'] == 'CRITICAL']
            if critical_violations:
                print(f"   {len(critical_violations)} CRITICAL violations need immediate action")
                
        if total_issues == 0:
            print("✓ All data integrity checks passed!")
            print("✓ System is ready for production monitoring")
        
        print()
        print("=" * 80)
        print(f"Check completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

def main():
    """Main function."""
    checker = DataIntegrityChecker()
    checker.run_integrity_check()
    
    # Return exit code based on severity of issues found
    critical_issues = (
        len([e for e in checker.results['calculation_errors'] if e.get('severity') == 'HIGH']) +
        len([v for v in checker.results['threshold_violations'] if v.get('severity') == 'CRITICAL']) +
        len([i for i in checker.results['data_quality_issues'] if i.get('severity') == 'HIGH'])
    )
    
    return 0 if critical_issues == 0 else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)