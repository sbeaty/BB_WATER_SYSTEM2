from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from datetime import datetime
import sqlite3
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

Base = declarative_base()

class Contact(Base):
    __tablename__ = 'contacts'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    msisdn = Column(String(20), nullable=False)
    group = Column(String(50), nullable=False)
    role = Column(String(50))
    dow = Column(String(20), default='ALL')  # Days of week
    window_start = Column(String(5), default='00:00')
    window_end = Column(String(5), default='23:59')
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Threshold(Base):
    __tablename__ = 'thresholds'
    
    id = Column(Integer, primary_key=True)
    threshold_ref = Column(String(100), nullable=False, unique=True)
    limit_value = Column(Float, nullable=False)
    comparison_operator = Column(String(10), nullable=False)
    target = Column(String(50), nullable=False)  # day_total, shift_total, absolute_value
    severity = Column(String(20), nullable=False)  # critical, warn, medium
    message_template = Column(Text, nullable=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AlarmLog(Base):
    __tablename__ = 'alarm_logs'
    
    id = Column(Integer, primary_key=True)
    threshold_ref = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    limit_value = Column(Float, nullable=False)
    severity = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    shift_type = Column(String(10))  # 'day', 'shift'
    shift_start = Column(DateTime)
    shift_end = Column(DateTime)
    triggered_at = Column(DateTime, default=datetime.utcnow)
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime)
    acknowledged_by = Column(String(100))

class DeliveryLog(Base):
    __tablename__ = 'delivery_logs'
    
    id = Column(Integer, primary_key=True)
    alarm_log_id = Column(Integer)  # Reference to alarm_log
    msisdn = Column(String(20), nullable=False)
    message_id = Column(String(100))  # Twilio message SID
    status = Column(String(50), nullable=False)  # sent, delivered, failed, etc.
    plc_name = Column(String(100))
    tag_name = Column(String(100))
    severity = Column(String(20))
    sent_at = Column(DateTime, default=datetime.utcnow)
    delivered_at = Column(DateTime)

class SystemConfig(Base):
    __tablename__ = 'system_config'
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), nullable=False, unique=True)
    value = Column(Text)
    description = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DatabaseManager:
    def __init__(self, db_path='water_monitoring.db'):
        self.db_path = db_path
        # Add connection pooling and timeout settings for better concurrency
        self.engine = create_engine(
            f'sqlite:///{db_path}',
            echo=False,
            connect_args={
                'check_same_thread': False,
                'timeout': 30
            },
            poolclass=NullPool  # Use NullPool to avoid connection pooling issues with SQLite
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Enable WAL mode for better concurrent access
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
        
    def create_tables(self):
        """Create all tables in the database."""
        Base.metadata.create_all(bind=self.engine)
        
    def get_session(self):
        """Get a database session."""
        return self.SessionLocal()
        
    def init_default_data(self):
        """Initialize database with default configuration data."""
        session = self.get_session()
        
        try:
            # Check if we already have data
            if session.query(SystemConfig).first():
                return
                
            # Add default system configuration with environment variables as defaults
            default_configs = [
                SystemConfig(key='twilio_sid', value=os.getenv('TWILIO_ACCOUNT_SID', ''), description='Twilio Account SID'),
                SystemConfig(key='twilio_token', value=os.getenv('TWILIO_AUTH_TOKEN', ''), description='Twilio Auth Token'),
                SystemConfig(key='twilio_from', value=os.getenv('TWILIO_FROM_NUMBER', ''), description='Twilio From Number'),
                SystemConfig(key='timezone', value='Pacific/Auckland', description='System Timezone'),
                SystemConfig(key='test_mode', value='true', description='Enable test mode'),
                SystemConfig(key='test_numbers', value='+64123456789', description='Test phone numbers (comma separated)'),
                SystemConfig(key='historian_server', value='192.168.10.236', description='SQL Server hostname/IP'),
                SystemConfig(key='historian_database', value='Runtime', description='Historian database name'),
                SystemConfig(key='historian_username', value='wwUser', description='Database username'),
                SystemConfig(key='historian_password', value='wwUser', description='Database password'),
            ]
            
            for config in default_configs:
                session.add(config)
                
            session.commit()
            print("Default system configuration created.")
            
        except Exception as e:
            session.rollback()
            print(f"Error initializing default data: {e}")
        finally:
            session.close()
            
    def import_contacts_from_csv(self, csv_path):
        """Import contacts from CSV file."""
        import csv
        session = self.get_session()
        
        try:
            # Clear existing contacts
            session.query(Contact).delete()
            
            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if not row.get('name') or not row['name'].strip():  # Skip empty rows
                        continue
                        
                    contact = Contact(
                        name=row['name'].strip() if row['name'] else '',
                        msisdn=row['msisdn'].strip() if row['msisdn'] else '',
                        group=row['group'].strip() if row['group'] else '',
                        role=row.get('role', '').strip() if row.get('role') else '',
                        dow=(row.get('dow') or 'ALL').strip() if row.get('dow') else 'ALL',
                        window_start=(row.get('window_start') or '00:00').strip() if row.get('window_start') else '00:00',
                        window_end=(row.get('window_end') or '23:59').strip() if row.get('window_end') else '23:59',
                        enabled=str(row.get('enabled', 'true')).lower() == 'true'
                    )
                    session.add(contact)
                    
            session.commit()
            count = session.query(Contact).count()
            print(f"Imported {count} contacts from CSV.")
            
        except Exception as e:
            session.rollback()
            print(f"Error importing contacts: {e}")
        finally:
            session.close()
            
    def import_thresholds_from_csv(self, csv_path):
        """Import thresholds from CSV file."""
        import csv
        session = self.get_session()
        
        try:
            # Clear existing thresholds
            session.query(Threshold).delete()
            
            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if not row['threshold_ref'].strip():  # Skip empty rows
                        continue
                        
                    threshold = Threshold(
                        threshold_ref=row['threshold_ref'].strip(),
                        limit_value=float(row['limit_value']),
                        comparison_operator=row['comparison_operator'].strip(),
                        target=row['target'].strip(),
                        severity=row['severity'].strip(),
                        message_template=row['message_template'].strip(),
                        enabled=True
                    )
                    session.add(threshold)
                    
            session.commit()
            count = session.query(Threshold).count()
            print(f"Imported {count} thresholds from CSV.")
            
        except Exception as e:
            session.rollback()
            print(f"Error importing thresholds: {e}")
        finally:
            session.close()

if __name__ == "__main__":
    # Initialize database
    db_manager = DatabaseManager()
    db_manager.create_tables()
    db_manager.init_default_data()
    
    # Import CSV data if files exist
    if os.path.exists('cc_contacts.csv'):
        db_manager.import_contacts_from_csv('cc_contacts.csv')
    
    if os.path.exists('ccv_thresholds.csv'):
        db_manager.import_thresholds_from_csv('ccv_thresholds.csv')
        
    print("Database initialization complete!")