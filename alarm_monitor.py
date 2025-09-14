import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any
import signal
import sys

from database import DatabaseManager, Contact, Threshold, AlarmLog, DeliveryLog, SystemConfig
from shift_calculator import ShiftCalculator
from sql_historian_client import SQLHistorianClient, HistorianConfig
from sms_router import SMSRouter
import json

class AlarmMonitor:
    """Background service that monitors water usage and sends alerts when thresholds are exceeded."""
    
    def __init__(self, check_interval=30):  # Check every 30 seconds
        self.check_interval = check_interval
        self.running = False
        self.thread = None
        
        self.db_manager = DatabaseManager()
        self.shift_calc = ShiftCalculator()
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\nReceived signal {signum}. Shutting down gracefully...")
        self.stop()
        sys.exit(0)
        
    def _get_system_config(self):
        """Load system configuration from database."""
        session = self.db_manager.get_session()
        try:
            configs = session.query(SystemConfig).all()
            config_dict = {config.key: config.value for config in configs}
            return config_dict
        finally:
            session.close()
            
    def _get_historian_config(self, config_dict):
        """Create historian configuration from system settings."""
        return HistorianConfig(
            server=config_dict.get('historian_server', '192.168.10.236'),
            database=config_dict.get('historian_database', 'Runtime'),
            username=config_dict.get('historian_username', 'wwUser'),
            password=config_dict.get('historian_password', 'wwUser')
        )
        
    def _create_app_config(self, config_dict):
        """Create app configuration object for SMS router."""
        from config_loader import AppConfig
        
        app_config = AppConfig()
        app_config.twilio_sid = config_dict.get('twilio_sid', '')
        app_config.twilio_token = config_dict.get('twilio_token', '')
        app_config.twilio_from = config_dict.get('twilio_from', '')
        app_config.timezone = config_dict.get('timezone', 'Pacific/Auckland')
        app_config.test_mode = config_dict.get('test_mode', 'true').lower() == 'true'
        
        if config_dict.get('test_numbers'):
            app_config.test_numbers = [num.strip() for num in config_dict.get('test_numbers', '').split(',')]
        else:
            app_config.test_numbers = []
            
        # Load contacts from database
        session = self.db_manager.get_session()
        try:
            contacts = session.query(Contact).filter_by(enabled=True).all()
            app_config.contacts = contacts
        finally:
            session.close()
            
        return app_config
        
    def _check_threshold_cooldown(self, threshold_ref: str, cooldown_minutes: int = 15) -> bool:
        """Check if enough time has passed since the last alarm for this threshold."""
        session = self.db_manager.get_session()
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=cooldown_minutes)
            recent_alarm = session.query(AlarmLog).filter(
                AlarmLog.threshold_ref == threshold_ref,
                AlarmLog.triggered_at >= cutoff_time
            ).first()
            
            return recent_alarm is None  # True if no recent alarm (cooldown period passed)
        finally:
            session.close()
            
    def _log_alarm(self, threshold: Threshold, value: float, shift_info: Dict, target_type: str) -> AlarmLog:
        """Log an alarm to the database."""
        session = self.db_manager.get_session()
        try:
            # Format message using threshold template
            message = threshold.message_template.format(
                value=value,
                unit='L',  # Default unit
                limit=threshold.limit_value,
                severity=threshold.severity.upper()
            )
            
            alarm = AlarmLog(
                threshold_ref=threshold.threshold_ref,
                value=value,
                limit_value=threshold.limit_value,
                severity=threshold.severity,
                message=message,
                shift_type=target_type,
                shift_start=shift_info.get('start_time') if target_type == 'shift_total' else None,
                shift_end=shift_info.get('end_time') if target_type == 'shift_total' else None,
                triggered_at=datetime.utcnow()
            )
            
            session.add(alarm)
            session.commit()
            session.refresh(alarm)
            return alarm
            
        except Exception as e:
            session.rollback()
            print(f"Error logging alarm: {e}")
            raise
        finally:
            session.close()
            
    def _send_alarm_notifications(self, alarm: AlarmLog, threshold: Threshold):
        """Send SMS notifications for an alarm."""
        try:
            # Load system configuration
            config_dict = self._get_system_config()
            app_config = self._create_app_config(config_dict)
            
            # Create SMS router
            sms_router = SMSRouter(app_config)
            
            # Create alert action structure for SMS router
            alert_action = {
                'threshold': threshold,
                'value': alarm.value,
                'plc_name': threshold.threshold_ref.replace('_day', '').replace('_shift', ''),
                'tag_config': self._create_tag_config(threshold)
            }
            
            # Send SMS
            session = self.db_manager.get_session()
            try:
                sms_router.send_alert(alert_action, session)
                print(f"SMS notifications sent for alarm: {threshold.threshold_ref}")
            finally:
                session.close()
                
        except Exception as e:
            print(f"Error sending alarm notifications: {e}")
            
    def _create_tag_config(self, threshold: Threshold):
        """Create a tag config object for SMS router compatibility."""
        from config_loader import TagConfig
        
        # Determine group based on threshold reference
        if 'PC' in threshold.threshold_ref or 'CK' in threshold.threshold_ref or 'FT51' in threshold.threshold_ref or 'FT31' in threshold.threshold_ref:
            group = 'PC and CK'
        elif 'TC' in threshold.threshold_ref or 'Ext' in threshold.threshold_ref or 'FT41' in threshold.threshold_ref or 'FT35' in threshold.threshold_ref:
            group = 'TC and Ext'
        elif 'DAF' in threshold.threshold_ref or 'Hot' in threshold.threshold_ref or 'FM82' in threshold.threshold_ref:
            group = 'DAF and Hot water'
        else:
            group = 'operations'  # Default group
            
        tag_config = TagConfig()
        tag_config.tag_name = threshold.threshold_ref
        tag_config.description = threshold.message_template
        tag_config.group = group
        tag_config.unit = 'L'
        tag_config.comparison_operator = threshold.comparison_operator
        tag_config.comparison_target = threshold.target
        
        return tag_config
        
    def _check_thresholds(self):
        """Check all active thresholds for violations."""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting threshold check...")
        
        session = self.db_manager.get_session()
        try:
            # Get all active thresholds
            thresholds = session.query(Threshold).filter_by(enabled=True).all()
            
            if not thresholds:
                print("No active thresholds found.")
                return
                
            # Get current shift and day information
            current_shift = self.shift_calc.get_current_shift_info()
            day_start, day_end = self.shift_calc.get_current_day_times()
            
            # Load system configuration
            config_dict = self._get_system_config()
            historian_config = self._get_historian_config(config_dict)
            
            violations_found = 0
            
            # Check each threshold
            with SQLHistorianClient(historian_config) as historian:
                for threshold in thresholds:
                    try:
                        # Extract tag name from threshold reference
                        tag_name = threshold.threshold_ref.replace('_day', '').replace('_shift', '')
                        
                        # Get target value based on threshold type
                        target_value = None
                        
                        if threshold.target == 'shift_total':
                            shift_delta = historian.get_tag_delta(tag_name, current_shift['start_time'], current_shift['end_time'])
                            target_value = shift_delta.get('delta', 0)
                        elif threshold.target == 'day_total':
                            day_delta = historian.get_tag_delta(tag_name, day_start, day_end)
                            target_value = day_delta.get('delta', 0)
                        elif threshold.target == 'absolute_value':
                            current_value_result = historian.get_tag_current_value(tag_name)
                            target_value = current_value_result.get('value', 0)
                            
                        if target_value is None:
                            continue
                            
                        # Check if threshold is exceeded
                        threshold_exceeded = False
                        if threshold.comparison_operator == '>=':
                            threshold_exceeded = target_value >= threshold.limit_value
                        elif threshold.comparison_operator == '>':
                            threshold_exceeded = target_value > threshold.limit_value
                        elif threshold.comparison_operator == '<=':
                            threshold_exceeded = target_value <= threshold.limit_value
                        elif threshold.comparison_operator == '<':
                            threshold_exceeded = target_value < threshold.limit_value
                            
                        if threshold_exceeded:
                            # Check cooldown period to prevent spam
                            cooldown_minutes = 15 if threshold.severity == 'warn' else 30  # Critical alarms have longer cooldown
                            
                            if self._check_threshold_cooldown(threshold.threshold_ref, cooldown_minutes):
                                print(f"THRESHOLD VIOLATION: {threshold.threshold_ref} = {target_value:.1f} {threshold.comparison_operator} {threshold.limit_value}")
                                
                                # Log the alarm
                                alarm = self._log_alarm(threshold, target_value, current_shift, threshold.target)
                                
                                # Send notifications
                                self._send_alarm_notifications(alarm, threshold)
                                
                                violations_found += 1
                            else:
                                print(f"Threshold violation detected for {threshold.threshold_ref} but cooldown period active.")
                                
                    except Exception as e:
                        print(f"Error checking threshold {threshold.threshold_ref}: {e}")
                        continue
                        
            print(f"Threshold check completed. {violations_found} new violations found.")
            
        except Exception as e:
            print(f"Error during threshold check: {e}")
        finally:
            session.close()
            
    def _monitor_loop(self):
        """Main monitoring loop."""
        print(f"Alarm monitor started. Check interval: {self.check_interval} seconds")
        
        while self.running:
            try:
                self._check_thresholds()
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                
            # Wait for next check
            for _ in range(self.check_interval):
                if not self.running:
                    break
                time.sleep(1)
                
        print("Alarm monitor stopped.")
        
    def start(self):
        """Start the alarm monitoring service."""
        if self.running:
            print("Alarm monitor is already running.")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        print("Alarm monitor started in background.")
        
    def stop(self):
        """Stop the alarm monitoring service."""
        if not self.running:
            return
            
        print("Stopping alarm monitor...")
        self.running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
            
        print("Alarm monitor stopped.")
        
    def is_running(self):
        """Check if the monitoring service is running."""
        return self.running and self.thread and self.thread.is_alive()

def main():
    """Main function for running the alarm monitor as a standalone service."""
    print("Water Monitoring Alarm Service")
    print("==============================")
    
    # Initialize database
    db_manager = DatabaseManager()
    db_manager.create_tables()
    
    # Create and start monitor
    monitor = AlarmMonitor(check_interval=30)  # Check every 30 seconds
    
    try:
        monitor.start()
        
        # Keep the main thread alive
        print("Press Ctrl+C to stop the service...")
        while monitor.is_running():
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nShutdown requested...")
    finally:
        monitor.stop()
        print("Service stopped.")

if __name__ == "__main__":
    main()