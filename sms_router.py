import datetime
import pytz
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from config_loader import AppConfig, ContactConfig, TagConfig, ThresholdConfig
import database as db

# Mapping from datetime.weekday() to 3-letter day strings
DOW_MAP = {0: 'MON', 1: 'TUE', 2: 'WED', 3: 'THU', 4: 'FRI', 5: 'SAT', 6: 'SUN'}

class SMSRouter:
    """Handles formatting and routing of SMS alerts via Twilio."""

    def __init__(self, twilio_sid=None, twilio_token=None, twilio_from=None, test_mode=False, config=None):
        """Initialize SMS router with either direct params or AppConfig object."""
        if config:
            # Initialize from AppConfig object
            self.config = config
            self.twilio_sid = config.twilio_sid
            self.twilio_token = config.twilio_token
            self.twilio_from = config.twilio_from
            self.test_mode = config.test_mode
        else:
            # Initialize from direct parameters
            self.config = None
            self.twilio_sid = twilio_sid
            self.twilio_token = twilio_token
            self.twilio_from = twilio_from
            self.test_mode = test_mode
            
        if self.twilio_sid and self.twilio_token:
            self.twilio_client = Client(self.twilio_sid, self.twilio_token)
            print(f"Twilio client initialized (test_mode={self.test_mode})")
        else:
            self.twilio_client = None
            print("Warning: Twilio credentials not found. SMS sending will be disabled.")

    def _format_message(self, alert_action: Dict[str, Any]) -> str:
        """Formats the SMS message using the configured template."""
        tag_config: TagConfig = alert_action['tag_config']
        threshold: ThresholdConfig = alert_action['threshold']
        value = alert_action['value']
        plc_name = alert_action['plc_name']

        # Round the value for cleaner display
        display_value = round(value, 2) if isinstance(value, float) else value

        # Basic template is a fallback
        template = threshold.message_template or "[{severity}] {tag_desc} is {value}{unit}"

        return template.format(
            severity=threshold.severity.upper(),
            plc_name=plc_name,
            tag_name=tag_config.tag_name,
            tag_desc=tag_config.description,
            target=threshold.target or tag_config.comparison_target,
            value=display_value,
            unit=tag_config.unit,
            limit=threshold.limit_value,
            op=threshold.comparison_operator or tag_config.comparison_operator
        )

    def _find_recipients(self, group: str) -> List[str]:
        """Finds all active contacts for a given group at the current time."""
        recipients = []
        tz = pytz.timezone(self.config.timezone)
        now = datetime.datetime.now(tz)
        now_time = now.time()
        today_dow = DOW_MAP[now.weekday()]

        for contact in self.config.contacts:
            if not contact.enabled or contact.group != group:
                continue

            # Check Day of Week
            contact_dows = [d.strip() for d in contact.dow.upper().split(',')]
            if 'ALL' not in contact_dows and today_dow not in contact_dows:
                continue

            # Check Time Window
            try:
                start_time = datetime.datetime.strptime(contact.window_start, '%H:%M').time()
                end_time = datetime.datetime.strptime(contact.window_end, '%H:%M').time()

                in_window = False
                if start_time <= end_time:
                    # Normal window (e.g., 09:00-17:00)
                    if start_time <= now_time < end_time:
                        in_window = True
                else:
                    # Overnight window (e.g., 22:00-06:00)
                    if now_time >= start_time or now_time < end_time:
                        in_window = True
                
                if in_window:
                    recipients.append(contact.msisdn)

            except ValueError:
                print(f"Warning: Invalid time format for contact {contact.name}. Skipping.")
                continue
        
        return list(set(recipients)) # Return unique list of numbers

    def send_alert(self, alert_action: Dict[str, Any], db_session: Session):
        """Sends an alert to the appropriate recipients."""
        if not self.twilio_client:
            print("SMS not sent: Twilio client is not configured.")
            return

        message_body = self._format_message(alert_action)
        tag_config: TagConfig = alert_action['tag_config']

        if self.config.test_mode:
            recipients = self.config.test_numbers
            print(f"TEST MODE: Routing alert for '{tag_config.tag_name}' to {recipients}")
        else:
            recipients = self._find_recipients(tag_config.group)
            print(f"Found {len(recipients)} recipients for group '{tag_config.group}'")

        if not recipients:
            print(f"No recipients found for alert on tag '{tag_config.tag_name}'.")
            return

        for number in recipients:
            log_status = 'failed'
            message_sid = None
            try:
                print(f"Sending SMS to {number}")
                message = self.twilio_client.messages.create(
                    to=number,
                    from_=self.config.twilio_from,
                    body=message_body
                )
                log_status = message.status
                message_sid = message.sid
                print(f"  -> SMS sent successfully. SID: {message_sid}")

            except TwilioRestException as e:
                print(f"Error sending SMS to {number}: {e}")
                log_status = f"failed: {e.code}"
            except Exception as e:
                print(f"An unexpected error occurred sending SMS to {number}: {e}")
                log_status = "failed: unknown error"

            # Log the delivery attempt to the database
            log_entry = db.DeliveryLog(
                msisdn=number,
                message_id=message_sid,
                status=log_status,
                plc_name=alert_action['plc_name'],
                tag_name=tag_config.tag_name,
                severity=alert_action['threshold'].severity
            )
            db_session.add(log_entry)
        
        db_session.commit()
    
    def send_sms(self, to_number, message_body):
        """Send a simple SMS message to a phone number."""
        if self.test_mode:
            print(f"TEST MODE: Would send SMS to {to_number}: {message_body}")
            return (True, "test-mode-no-sid")
        
        if not self.twilio_client:
            print("Error: Twilio client not initialized")
            return (False, "no-twilio-client")
        
        try:
            print(f"Sending SMS to {to_number}")
            print(f"Message: {message_body}")
            message = self.twilio_client.messages.create(
                to=to_number,
                from_=self.twilio_from,
                body=message_body
            )
            print(f"SMS sent successfully. SID: {message.sid}")
            return (True, message.sid)
        except TwilioRestException as e:
            print(f"Twilio error sending SMS: {e}")
            return (False, str(e))
        except Exception as e:
            print(f"Unexpected error sending SMS: {e}")
            return (False, str(e))
