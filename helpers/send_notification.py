import smtplib, ssl
from load_config import *

def send_notification(coin, secret_config):

    port = 465  # For SSL
    smtp_server = secret_config['smtp_server']
    sent_from = secret_config['sender_email']
    to = [secret_config['receiver_email']]
    subject = f'Possible new coin detected {coin}'
    body = f'New coin detected {coin}'
    message = 'Subject: {}\n\n{}'.format(subject, body)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
            server.login(sent_from, secret_config['password'])
            server.sendmail(sent_from, to, message)

    except Exception as e:
        print(e)