from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from datetime import datetime, timedelta
import os
from database import DatabaseManager, Contact, Threshold, AlarmLog, DeliveryLog, SystemConfig
from shift_calculator import ShiftCalculator
from sql_historian_client import SQLHistorianClient, HistorianConfig
from sms_router import SMSRouter
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import tag mapping functionality
try:
    from tag_mapping import get_database_tag_name, get_tag_info
except ImportError:
    # If tag_mapping not available, create a simple fallback
    def get_database_tag_name(tag_name):
        return tag_name
    def get_tag_info(tag_name):
        return {'db_tag': tag_name, 'description': tag_name, 'line': 'Unknown'}

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'  # Change this in production

# Add min function to Jinja2 template globals
app.jinja_env.globals.update(min=min)

# Initialize database
db_manager = DatabaseManager()
shift_calc = ShiftCalculator()

@app.route('/')
def dashboard():
    """Main dashboard showing live water usage data."""
    import time
    start_time = time.time()
    
    session = db_manager.get_session()
    
    try:
        # Get current shift and day information
        current_shift = shift_calc.get_current_shift_info()
        day_start, day_end = shift_calc.get_current_day_times()
        
        # Get all thresholds - now using batch queries for efficiency
        thresholds = session.query(Threshold).filter_by(enabled=True).all()
        print(f"Dashboard: Found {len(thresholds)} thresholds")
        query_time = time.time() - start_time
        print(f"Dashboard: Query completed in {query_time:.2f} seconds")
        
        # Get recent alarms (last 24 hours)
        recent_alarms = session.query(AlarmLog).filter(
            AlarmLog.triggered_at >= datetime.utcnow() - timedelta(days=1)
        ).order_by(AlarmLog.triggered_at.desc()).limit(50).all()
        
        # Get system configuration
        historian_config = get_historian_config(session)
        print(f"Dashboard: Connecting to historian at {historian_config.server}")
        
        # Collect live data for all thresholds with timeout handling
        historian_start_time = time.time()
        live_data = []
        try:
            print(f"Dashboard: Connecting to historian...")
            with SQLHistorianClient(historian_config) as historian:
                print(f"Dashboard: Connected in {time.time() - historian_start_time:.2f} seconds")
                
                # OPTIMIZATION: Collect all unique database tag names first
                batch_start_time = time.time()
                all_db_tag_names = []
                threshold_tag_mapping = {}  # threshold_id -> (tag_name, db_tag_name, tag_info)
                
                for threshold in thresholds:
                    tag_name = threshold.threshold_ref.replace('_day', '').replace('_shift', '')
                    tag_info = get_tag_info(tag_name)
                    db_tag_name = tag_info['db_tag']
                    
                    if db_tag_name not in all_db_tag_names:
                        all_db_tag_names.append(db_tag_name)
                    
                    threshold_tag_mapping[threshold.id] = (tag_name, db_tag_name, tag_info)
                
                # SINGLE BATCH QUERY: Get all current values at once
                print(f"Dashboard: Batch querying {len(all_db_tag_names)} unique tags...")
                current_values_batch = historian.get_multiple_tags_batch(all_db_tag_names)
                print(f"Dashboard: Batch query completed in {time.time() - batch_start_time:.2f} seconds")
                
                # Now process each threshold with the batch data
                for i, threshold in enumerate(thresholds):
                    try:
                        threshold_start_time = time.time()
                        print(f"Processing threshold {i+1}/{len(thresholds)}: {threshold.threshold_ref}")
                        
                        tag_name, db_tag_name, tag_info = threshold_tag_mapping[threshold.id]
                        
                        # Get current value from batch results
                        current_value_result = current_values_batch.get(db_tag_name, {'value': None, 'success': False})
                        
                        # Calculate both shift and day totals for all thresholds
                        shift_total = 0
                        day_total = 0
                        
                        # SMART OPTIMIZATION: Only calculate deltas for critical/warn severity thresholds
                        # For others, just show current values to speed up loading
                        if threshold.severity in ['critical', 'warn'] and threshold.target in ['shift_total', 'day_total']:
                            if threshold.target == 'shift_total':
                                shift_start_time = time.time()
                                try:
                                    shift_delta = historian.get_tag_delta(db_tag_name, current_shift['start_time'], current_shift['end_time'])
                                    shift_total = shift_delta.get('delta', 0)
                                    print(f"  Shift delta query (critical): {time.time() - shift_start_time:.2f}s")
                                except Exception as e:
                                    print(f"Error calculating shift total for {tag_name} ({db_tag_name}): {e}")
                            elif threshold.target == 'day_total':
                                day_start_time = time.time()
                                try:
                                    day_delta = historian.get_tag_delta(db_tag_name, day_start, day_end)
                                    day_total = day_delta.get('delta', 0)
                                    print(f"  Day delta query (critical): {time.time() - day_start_time:.2f}s")
                                except Exception as e:
                                    print(f"Error calculating day total for {tag_name} ({db_tag_name}): {e}")
                        else:
                            print(f"  Skipping expensive calculations for {threshold.severity} threshold")
                        # For absolute_value targets or low-priority thresholds, we just use the current value
                            
                        print(f"  Total threshold processing: {time.time() - threshold_start_time:.2f}s")
                                
                        # Check if threshold is exceeded
                        target_value = shift_total if threshold.target == 'shift_total' else day_total if threshold.target == 'day_total' else current_value_result.get('value', 0)
                        
                        threshold_exceeded = False
                        if target_value and threshold.limit_value:
                            if threshold.comparison_operator == '>=':
                                threshold_exceeded = target_value >= threshold.limit_value
                            elif threshold.comparison_operator == '>':
                                threshold_exceeded = target_value > threshold.limit_value
                            elif threshold.comparison_operator == '<=':
                                threshold_exceeded = target_value <= threshold.limit_value
                            elif threshold.comparison_operator == '<':
                                threshold_exceeded = target_value < threshold.limit_value
                        
                        live_data.append({
                            'threshold': threshold,
                            'current_value': current_value_result.get('value'),
                            'shift_total': shift_total,
                            'day_total': day_total,
                            'target_value': target_value,
                            'threshold_exceeded': threshold_exceeded,
                            'unit': current_value_result.get('unit', ''),
                            'last_updated': current_value_result.get('timestamp'),
                            'tag_name': tag_name,
                            'tag_info': tag_info
                        })
                        
                    except Exception as e:
                        print(f"Error processing threshold {threshold.threshold_ref}: {e}")
                        # Add placeholder data for failed threshold
                        tag_name = threshold.threshold_ref.replace('_day', '').replace('_shift', '')
                        tag_info = get_tag_info(tag_name)
                        live_data.append({
                            'threshold': threshold,
                            'current_value': None,
                            'shift_total': None,
                            'day_total': None,
                            'target_value': None,
                            'threshold_exceeded': False,
                            'unit': '',
                            'last_updated': None,
                            'tag_name': tag_name,
                            'tag_info': tag_info
                        })
                        continue
        except Exception as e:
            print(f'Historian connection error: {str(e)}')
            # Return minimal data structure on connection failure
        
        # Group live data by manufacturing line
        lines_data = {}
        for item in live_data:
            line = item['tag_info']['line']
            if line not in lines_data:
                lines_data[line] = []
            lines_data[line].append(item)
        
        # Sort lines by priority
        line_order = ['PC Line', 'CK Line', 'TC Line', 'EP Line', 'Utilities', 'Test', 'Unknown']
        sorted_lines = sorted(lines_data.items(), key=lambda x: line_order.index(x[0]) if x[0] in line_order else len(line_order))
        
        # Log total execution time
        total_time = time.time() - start_time
        print(f"Dashboard loaded in {total_time:.2f} seconds")
        
        return render_template('dashboard.html',
                             current_shift=current_shift,
                             day_start=day_start,
                             day_end=day_end,
                             live_data=live_data,
                             lines_data=sorted_lines,
                             recent_alarms=recent_alarms)
                             
    except Exception as e:
        print(f'Dashboard error: {str(e)}')
        flash(f'Error loading dashboard: {str(e)}', 'error')
        # Return with empty data but proper structure
        return render_template('dashboard.html', 
                             live_data=[], 
                             recent_alarms=[],
                             current_shift=shift_calc.get_current_shift_info() if 'shift_calc' in locals() else None,
                             day_start=datetime.now(),
                             day_end=datetime.now() + timedelta(days=1))
    finally:
        session.close()

@app.route('/api/live-data')
def api_live_data():
    """API endpoint for live data updates."""
    session = db_manager.get_session()
    
    try:
        current_shift = shift_calc.get_current_shift_info()
        day_start, day_end = shift_calc.get_current_day_times()
        
        thresholds = session.query(Threshold).filter_by(enabled=True).all()
        historian_config = get_historian_config(session)
        
        data = []
        with SQLHistorianClient(historian_config) as historian:
            for threshold in thresholds:
                tag_name = threshold.threshold_ref.replace('_day', '').replace('_shift', '')
                db_tag_name = get_database_tag_name(tag_name)
                current_value_result = historian.get_tag_current_value(db_tag_name)
                
                shift_total = 0
                day_total = 0
                
                # Always calculate both shift and day totals for display
                try:
                    shift_delta = historian.get_tag_delta(db_tag_name, current_shift['start_time'], current_shift['end_time'])
                    shift_total = shift_delta.get('delta', 0)
                except Exception as e:
                    print(f"API: Error calculating shift total for {tag_name} ({db_tag_name}): {e}")
                
                try:
                    day_delta = historian.get_tag_delta(db_tag_name, day_start, day_end)
                    day_total = day_delta.get('delta', 0)
                except Exception as e:
                    print(f"API: Error calculating day total for {tag_name} ({db_tag_name}): {e}")
                
                target_value = shift_total if threshold.target == 'shift_total' else day_total if threshold.target == 'day_total' else current_value_result.get('value', 0)
                
                threshold_exceeded = False
                if target_value and threshold.limit_value:
                    if threshold.comparison_operator == '>=':
                        threshold_exceeded = target_value >= threshold.limit_value
                    elif threshold.comparison_operator == '>':
                        threshold_exceeded = target_value > threshold.limit_value
                    elif threshold.comparison_operator == '<=':
                        threshold_exceeded = target_value <= threshold.limit_value
                    elif threshold.comparison_operator == '<':
                        threshold_exceeded = target_value < threshold.limit_value
                        
                data.append({
                    'threshold_ref': threshold.threshold_ref,
                    'current_value': current_value_result.get('value'),
                    'shift_total': round(shift_total, 2) if shift_total else 0,
                    'day_total': round(day_total, 2) if day_total else 0,
                    'target_value': round(target_value, 2) if target_value else 0,
                    'limit_value': threshold.limit_value,
                    'threshold_exceeded': threshold_exceeded,
                    'severity': threshold.severity,
                    'unit': current_value_result.get('unit', ''),
                    'last_updated': current_value_result.get('timestamp').isoformat() if current_value_result.get('timestamp') else None
                })
        
        return jsonify({
            'success': True,
            'data': data,
            'current_shift': {
                'name': current_shift['shift_name'],
                'start_time': current_shift['start_time'].isoformat(),
                'end_time': current_shift['end_time'].isoformat()
            },
            'updated_at': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session.close()

@app.route('/thresholds')
def thresholds():
    """Threshold management page."""
    session = db_manager.get_session()
    try:
        thresholds = session.query(Threshold).order_by(Threshold.threshold_ref).all()
        return render_template('thresholds.html', thresholds=thresholds)
    finally:
        session.close()

@app.route('/thresholds/edit/<int:threshold_id>', methods=['GET', 'POST'])
def edit_threshold(threshold_id):
    """Edit threshold settings."""
    session = db_manager.get_session()
    
    try:
        threshold = session.query(Threshold).get(threshold_id)
        if not threshold:
            flash('Threshold not found', 'error')
            return redirect(url_for('thresholds'))
        
        if request.method == 'POST':
            threshold.limit_value = float(request.form['limit_value'])
            threshold.comparison_operator = request.form['comparison_operator']
            threshold.target = request.form['target']
            threshold.severity = request.form['severity']
            threshold.message_template = request.form['message_template']
            threshold.enabled = 'enabled' in request.form
            threshold.updated_at = datetime.utcnow()
            
            session.commit()
            flash('Threshold updated successfully', 'success')
            return redirect(url_for('thresholds'))
        
        return render_template('edit_threshold.html', threshold=threshold)
        
    except Exception as e:
        session.rollback()
        flash(f'Error updating threshold: {str(e)}', 'error')
        return redirect(url_for('thresholds'))
    finally:
        session.close()

@app.route('/contacts')
def contacts():
    """Contact management page."""
    session = db_manager.get_session()
    try:
        contacts = session.query(Contact).order_by(Contact.name).all()
        return render_template('contacts.html', contacts=contacts)
    finally:
        session.close()

@app.route('/contacts/add', methods=['GET', 'POST'])
def add_contact():
    """Add new contact."""
    if request.method == 'POST':
        session = db_manager.get_session()
        
        try:
            contact = Contact(
                name=request.form['name'],
                msisdn=request.form['msisdn'],
                group=request.form['group'],
                role=request.form.get('role', ''),
                dow=request.form.get('dow', 'ALL'),
                window_start=request.form.get('window_start', '00:00'),
                window_end=request.form.get('window_end', '23:59'),
                enabled='enabled' in request.form
            )
            
            session.add(contact)
            session.commit()
            flash('Contact added successfully', 'success')
            return redirect(url_for('contacts'))
            
        except Exception as e:
            session.rollback()
            flash(f'Error adding contact: {str(e)}', 'error')
        finally:
            session.close()
    
    return render_template('add_contact.html')

@app.route('/contacts/edit/<int:contact_id>', methods=['GET', 'POST'])
def edit_contact(contact_id):
    """Edit contact details."""
    session = db_manager.get_session()
    
    try:
        contact = session.query(Contact).get(contact_id)
        if not contact:
            flash('Contact not found', 'error')
            return redirect(url_for('contacts'))
        
        if request.method == 'POST':
            contact.name = request.form['name']
            contact.msisdn = request.form['msisdn']
            contact.group = request.form['group']
            contact.role = request.form.get('role', '')
            contact.dow = request.form.get('dow', 'ALL')
            contact.window_start = request.form.get('window_start', '00:00')
            contact.window_end = request.form.get('window_end', '23:59')
            contact.enabled = 'enabled' in request.form
            contact.updated_at = datetime.utcnow()
            
            session.commit()
            flash('Contact updated successfully', 'success')
            return redirect(url_for('contacts'))
        
        return render_template('edit_contact.html', contact=contact)
        
    except Exception as e:
        session.rollback()
        flash(f'Error updating contact: {str(e)}', 'error')
        return redirect(url_for('contacts'))
    finally:
        session.close()

@app.route('/contacts/delete/<int:contact_id>', methods=['POST'])
def delete_contact(contact_id):
    """Delete contact."""
    session = db_manager.get_session()
    
    try:
        contact = session.query(Contact).get(contact_id)
        if contact:
            session.delete(contact)
            session.commit()
            flash('Contact deleted successfully', 'success')
        else:
            flash('Contact not found', 'error')
    except Exception as e:
        session.rollback()
        flash(f'Error deleting contact: {str(e)}', 'error')
    finally:
        session.close()
    
    return redirect(url_for('contacts'))

@app.route('/alarms')
def alarms():
    """Alarm logs page."""
    session = db_manager.get_session()
    
    try:
        # Get query parameters for filtering
        days = request.args.get('days', 7, type=int)
        severity = request.args.get('severity', '')
        
        # Build query
        query = session.query(AlarmLog)
        
        # Filter by date
        if days > 0:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query = query.filter(AlarmLog.triggered_at >= cutoff_date)
        
        # Filter by severity
        if severity:
            query = query.filter(AlarmLog.severity == severity)
        
        alarms = query.order_by(AlarmLog.triggered_at.desc()).limit(200).all()
        
        return render_template('alarms.html', alarms=alarms, 
                             selected_days=days, selected_severity=severity)
    finally:
        session.close()

@app.route('/settings')
def settings():
    """System settings page."""
    session = db_manager.get_session()
    
    try:
        configs = session.query(SystemConfig).all()
        config_dict = {config.key: config.value for config in configs}
        return render_template('settings.html', config=config_dict)
    finally:
        session.close()

@app.route('/settings/test-sms', methods=['POST'])
def test_sms():
    """Send a test SMS to verify configuration."""
    session = db_manager.get_session()
    results = []
    
    try:
        # Get test configuration
        configs = session.query(SystemConfig).all()
        config_dict = {config.key: config.value for config in configs}
        
        test_mode = config_dict.get('test_mode', 'true').lower() == 'true'
        
        # Check if specific number provided in request (from contact edit page)
        test_numbers = request.form.get('test_numbers', '')
        
        # If not provided, use configured test numbers
        if not test_numbers:
            test_numbers = config_dict.get('test_numbers', '')
        
        if not test_numbers:
            return jsonify({
                'success': False, 
                'message': 'No test numbers configured'
            })
        
        # Special case: if +64275432868 is provided, disable test mode for this SMS
        force_real_sms = '+64275432868' in test_numbers
        effective_test_mode = test_mode and not force_real_sms
        
        # Initialize SMS router with environment variables as fallback
        from sms_router import SMSRouter
        twilio_sid = config_dict.get('twilio_sid') or os.getenv('TWILIO_ACCOUNT_SID', '')
        twilio_token = config_dict.get('twilio_token') or os.getenv('TWILIO_AUTH_TOKEN', '')
        twilio_from = config_dict.get('twilio_from') or os.getenv('TWILIO_FROM_NUMBER', '')
        
        print(f"Initializing SMS router:")
        print(f"  SID: {twilio_sid[:10]}..." if twilio_sid else "  SID: Not configured")
        print(f"  From: {twilio_from}")
        print(f"  Test mode: {effective_test_mode} (original: {test_mode}, force_real: {force_real_sms})")
        
        sms_router = SMSRouter(
            twilio_sid=twilio_sid,
            twilio_token=twilio_token,
            twilio_from=twilio_from,
            test_mode=effective_test_mode
        )
        
        # Send test message
        test_message = f"Test SMS from Water Monitoring System at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        for number in test_numbers.split(','):
            number = number.strip()
            if number:
                success, msg_id = sms_router.send_sms(number, test_message)
                if success:
                    results.append(f'Test SMS sent successfully to {number}')
                else:
                    results.append(f'Failed to send test SMS to {number}: {msg_id}')
        
        return jsonify({
            'success': True, 
            'message': '\n'.join(results)
        })
        
    except Exception as e:
        print(f"Error in test SMS: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'Error sending test SMS: {str(e)}'
        })
    finally:
        session.close()

@app.route('/settings/save', methods=['POST'])
def save_settings():
    """Save system settings."""
    session = db_manager.get_session()
    
    try:
        for key, value in request.form.items():
            config = session.query(SystemConfig).filter_by(key=key).first()
            if config:
                config.value = value
                config.updated_at = datetime.utcnow()
            else:
                config = SystemConfig(key=key, value=value)
                session.add(config)
        
        session.commit()
        flash('Settings saved successfully', 'success')
    except Exception as e:
        session.rollback()
        flash(f'Error saving settings: {str(e)}', 'error')
    finally:
        session.close()
    
    return redirect(url_for('settings'))

def get_historian_config(session):
    """Get historian configuration from database."""
    configs = session.query(SystemConfig).all()
    config_dict = {config.key: config.value for config in configs}
    
    return HistorianConfig(
        server=config_dict.get('historian_server', '192.168.10.236'),
        database=config_dict.get('historian_database', 'Runtime'),
        username=config_dict.get('historian_username', 'wwUser'),
        password=config_dict.get('historian_password', 'wwUser')
    )

if __name__ == '__main__':
    # Initialize database on startup
    db_manager.create_tables()
    db_manager.init_default_data()
    
    # Import CSV data if not already imported
    session = db_manager.get_session()
    try:
        if session.query(Contact).count() == 0 and os.path.exists('cc_contacts.csv'):
            db_manager.import_contacts_from_csv('cc_contacts.csv')
        
        if session.query(Threshold).count() == 0 and os.path.exists('ccv_thresholds.csv'):
            db_manager.import_thresholds_from_csv('ccv_thresholds.csv')
    finally:
        session.close()
    
    app.run(debug=True, host='127.0.0.1', port=5000)