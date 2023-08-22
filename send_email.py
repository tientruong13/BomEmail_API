from flask import Flask, request, jsonify
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
import imaplib
from email import encoders
from datetime import datetime, timedelta
import os
import base64
import smtplib
import uuid
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
if __name__ == '__main__':
    app.run(debug=True)
    
scheduler = BackgroundScheduler()
scheduler.start()
job_ids = {}


@app.route('/send_email', methods=['POST'])
def send_email():
    data = request.json
    name = data['name']
    email_from = data['emailFrom']
    password = data['passWord']
    recipients = data['emailTo']
    subject = data['Subject']
    body = data['body']
    attachments = data.get('attachs', [])
    schedule = data.get('Schedule', {})
    schedule_option = data.get('ScheduleOption', 'now').lower()
    quantity = int(data.get('quantily', 1))
    send_type = data.get('sendType', 'single').lower()

    if not isinstance(recipients, list):
        recipients = [recipients]

    send_datetime = None
    job_id = str(uuid.uuid4())
    
    if schedule_option == 'now':
        if send_type == 'single':
            for recipient in recipients:
                for _ in range(quantity):
                    send_mail(name, email_from, password, recipient, subject, body, attachments)
        elif send_type == 'multiple':
            for _ in range(quantity):
                send_mail(name, email_from, password, recipients, subject, body, attachments)
        return jsonify({'status': 'Email sent successfully'}), 200

    elif schedule_option == 'daily':
        send_time = schedule.get('Time', '00:00')
        send_datetime = datetime.combine(datetime.now().date(), datetime.strptime(send_time, '%H:%M').time())
        if send_type == 'single':
            for recipient in recipients:
                for _ in range(quantity):
                    job = scheduler.add_job(send_mail, 'interval', days=1, start_date=send_datetime, id=job_id,replace_existing=True, args=[name, email_from, password, recipient, subject, body, attachments])
        elif send_type == 'multiple':
            for _ in range(quantity):
                job = scheduler.add_job(send_mail, 'interval', days=1, start_date=send_datetime, id=job_id, replace_existing=True, args=[name, email_from, password, recipients, subject, body, attachments])

    elif schedule_option == 'weekly':
        send_time = schedule.get('Time', '00:00')
        hour, minute = map(int, send_time.split(":"))
        send_day_of_week = schedule.get('DayOfWeek', 'monday')
        send_datetime = datetime.combine(datetime.now().date(), datetime.strptime(send_time, '%H:%M').time())
        if send_type == 'single':
            for recipient in recipients:
                for _ in range(quantity):
                    job = scheduler.add_job(send_mail, 'cron', day_of_week=send_day_of_week, id=job_id, replace_existing=True, hour=hour, minute=minute, args=[name, email_from, password, recipient, subject, body, attachments])
        elif send_type == 'multiple':
            for _ in range(quantity):
                job = scheduler.add_job(send_mail, 'cron', day_of_week=send_day_of_week, id=job_id, replace_existing=True, hour=hour, minute=minute, args=[name, email_from, password, recipients, subject, body, attachments])
        

    elif schedule_option == 'monthly':
        send_time = schedule.get('Time', '00:00')
        hour, minute = map(int, send_time.split(":"))
        send_day = int(schedule.get('Day', 1))
        send_datetime = datetime.combine(datetime.now().replace(day=send_day).date(), datetime.strptime(send_time, '%H:%M').time())

        if send_type == 'single':
            for recipient in recipients:
                for _ in range(quantity):
                    job = scheduler.add_job(send_mail, 'cron', day=send_day, hour=hour, minute=minute, id=job_id, replace_existing=True, args=[name, email_from, password, recipient, subject, body, attachments])
        elif send_type == 'multiple':
            for _ in range(quantity):
                job = scheduler.add_job(send_mail, 'cron', day=send_day, hour=hour, minute=minute, id=job_id, replace_existing=True, args=[name, email_from, password, recipients, subject, body, attachments])
        
        
    elif schedule_option == 'custom':
        send_date = schedule.get('Date', datetime.now().date())
        send_time = schedule.get('Time', '00:00')
        send_datetime = datetime.strptime(f'{send_date} {send_time}', '%Y-%m-%d %H:%M')
        print(f"Send Time: {send_time}")
        print(f"Send Day of Week: {send_date}")
        print(f"Send DateTime: {send_datetime}")
        if send_type == 'single':
            for recipient in recipients:
                for _ in range(quantity):
                    job = scheduler.add_job(send_mail, 'date', run_date=send_datetime, id=job_id,replace_existing=True, args=[name, email_from, password, recipient, subject, body, attachments])
        elif send_type == 'multiple':
            for _ in range(quantity):
                job = scheduler.add_job(send_mail, 'date', run_date=send_datetime, id=job_id,replace_existing=True, args=[name, email_from, password, recipients, subject, body, attachments])
        # print(f"'next_run_time': {job.next_run_time}")
    
    if job_id not in job_ids:
        job_ids[job_id] = []
    job_ids[job_id].append(job.id)
    

    return jsonify({'status': 'Email scheduled successfully'}), 200

def delete_email(email_from, password, subject):
    # Connect to Gmail and select the mailbox
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(email_from, password)
    
    # Select the "sent" mailbox
    mail.select('"[Gmail]/Sent Mail"')
    
    # Search for the email
    search_criteria = f'SUBJECT "{subject}"'
    status, email_ids = mail.search(None, search_criteria)
    if status == 'OK':
        for e_id in email_ids[0].split():
            mail.store(e_id , '+FLAGS', '(\Deleted)')
        mail.expunge()


def send_mail(name, email_from, password, recipients, subject, body, attachments):
    msg = MIMEMultipart()
    msg['From'] = f"{name} <{email_from}>"
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))
    try:
        for attachment_path in attachments:
            if not os.path.exists(attachment_path):
                print(f"File not found: {attachment_path}")
                continue
            filename = os.path.basename(attachment_path)
            with open(attachment_path, 'rb') as f:
                decoded_file_content = f.read()

            part = MIMEBase('application', 'octet-stream')
            part.set_payload(decoded_file_content)
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment; filename= %s' % filename)
            msg.attach(part)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(email_from, password)
        text = msg.as_string()
        server.sendmail(email_from, recipients, text)
        delete_email(email_from, password, subject)
        server.quit()
        print("Email sent successfully!")
    except Exception as e:
        print(f"An error occurred: {e}")


@app.route('/cancel_email/<task_id>', methods=['POST'])
def cancel_email(task_id):
    print("Current job_ids:", job_ids)  
    print("Requested task_id to cancel:", task_id)
    
    if task_id in job_ids:
        for actual_job_id in job_ids[task_id]:
            scheduler.remove_job(actual_job_id)
        del job_ids[task_id]
        return jsonify({'status': 'Email schedule cancelled successfully'}), 200
    else:
        return jsonify({'status': 'No such task_id found'}), 404
    

@app.route('/list_active_jobs', methods=['GET'])
def list_active_jobs():
    active_jobs = []
    for task_id, jobs in job_ids.items():
        for job_id in jobs:
            job = scheduler.get_job(job_id)
            if job:  # Check if the job exists
                job_info = {
                    'task_id': task_id,
                    'job_id': job_id,
                    'next_run_time': str(job.next_run_time)
                }
                active_jobs.append(job_info)
    return jsonify(active_jobs), 200
