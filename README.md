# Water Monitoring System

A Flask-based water usage monitoring system with real-time data visualization, threshold management, and SMS alarm notifications.

## Features

- **Real-time Dashboard**: Live water usage data with threshold status
- **Shift Management**: Automatic calculation of 8-hour shifts (7 AM, 3 PM, 11 PM)
- **Threshold Management**: Configurable alarm thresholds for day/shift totals
- **Contact Management**: SMS notification contact lists with time windows
- **Alarm Logging**: Complete history of threshold violations
- **SMS Notifications**: Twilio-based text message alerts
- **Modern UI**: Responsive Tailwind CSS interface

## System Requirements

- Python 3.8+
- SQL Server with ODBC Driver 17
- Twilio account (for SMS notifications)
- Windows/Linux compatible

## Installation

1. **Clone/Download the Project**
   ```bash
   cd BB_WATER_SYSTEM2
   ```

2. **Install Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install SQL Server ODBC Driver** (if not already installed)
   - Download from Microsoft: [ODBC Driver 17 for SQL Server](https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)

4. **Initialize Database**
   ```bash
   python database.py
   ```

## Configuration

### 1. Database Setup

The system uses SQLite for configuration storage and connects to SQL Server for live data.

- Configuration database: `water_monitoring.db` (created automatically)
- Historian database: SQL Server (configured in settings)

### 2. Initial Data Import

The system will automatically import contacts and thresholds from CSV files on first run:

- `cc_contacts.csv` - Contact information
- `ccv_thresholds.csv` - Threshold configurations

### 3. System Settings

Access the Settings page in the web interface to configure:

- **Twilio SMS Settings**: Account SID, Auth Token, From Number
- **Database Connection**: SQL Server hostname, database, credentials
- **System Preferences**: Timezone, test mode

### 4. Twilio Configuration

1. Create account at [Twilio](https://www.twilio.com/)
2. Get Account SID and Auth Token from console
3. Purchase a phone number for sending SMS
4. Configure in Settings page

## Running the Application

### Web Interface

```bash
python app.py
```

Access the web interface at: `http://localhost:5000`

### Background Alarm Monitor

```bash
python alarm_monitor.py
```

This runs the background service that monitors thresholds and sends SMS alerts.

## Usage

### Dashboard

- View real-time water usage data
- Monitor threshold status for all systems
- See current shift information
- Check recent alarms

### Threshold Management

- Edit threshold values and comparison operators
- Enable/disable individual thresholds
- Modify alarm severity levels
- Update message templates

### Contact Management

- Add/edit notification contacts
- Set alert time windows and days
- Organize contacts by groups
- Enable/disable contacts

### Alarm History

- View complete alarm log
- Filter by time period and severity
- Track acknowledgment status

## Shift Schedule

The system operates on three 8-hour shifts:

- **Day Shift**: 7:00 AM - 3:00 PM
- **Afternoon Shift**: 3:00 PM - 11:00 PM
- **Night Shift**: 11:00 PM - 7:00 AM (next day)

## Database Schema

### Tables

- `contacts` - SMS notification contacts
- `thresholds` - Alarm threshold configurations
- `alarm_logs` - History of threshold violations
- `delivery_logs` - SMS delivery tracking
- `system_config` - System configuration settings

## CSV File Formats

### Contacts (cc_contacts.csv)

```csv
name,msisdn,group,role,dow,window_start,window_end,enabled
John Doe,+64211234567,PC and CK,Supervisor,ALL,00:00,23:59,true
```

### Thresholds (ccv_thresholds.csv)

```csv
threshold_ref,limit_value,comparison_operator,target,severity,message_template
FT5101_TotalLts_day,10000.0,>=,day_total,critical,PC Barrel Washer (24hr total: {value:.0f}{unit})
```

## API Endpoints

- `GET /api/live-data` - Real-time data for dashboard updates
- `POST /settings/save` - Save system settings
- Various CRUD endpoints for contacts, thresholds, etc.

## Security Considerations

- Change Flask secret key in production
- Secure Twilio credentials
- Restrict database access
- Use HTTPS in production
- Configure firewall appropriately

## Troubleshooting

### Database Connection Issues

1. Verify SQL Server is accessible
2. Check ODBC driver installation
3. Confirm credentials and database name
4. Test connection from Settings page

### SMS Not Working

1. Verify Twilio credentials
2. Check account balance
3. Ensure from number is valid
4. Test SMS from Settings page

### Missing Data

1. Check historian database connection
2. Verify tag names match database
3. Review time range calculations
4. Check shift calculations

## File Structure

```
BB_WATER_SYSTEM2/
├── app.py                 # Main Flask application
├── database.py            # Database models and management
├── shift_calculator.py    # Shift time calculations
├── alarm_monitor.py       # Background monitoring service
├── sms_router.py          # SMS notification handling
├── sql_historian_client.py # Database client for live data
├── config_loader.py       # Configuration data classes
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── templates/            # HTML templates
│   ├── base.html
│   ├── dashboard.html
│   ├── thresholds.html
│   ├── contacts.html
│   ├── alarms.html
│   └── settings.html
├── cc_contacts.csv       # Contact configuration
├── ccv_thresholds.csv    # Threshold configuration
└── water_monitoring.db   # SQLite configuration database
```

## Support

For issues or questions:

1. Check the troubleshooting section
2. Review log files for error messages
3. Verify all configuration settings
4. Test individual components (database, SMS, etc.)

## License

Internal use only - Water Processing Facility Monitoring System