from celery import Celery
import smtplib

EMAIL_ADDRESS = "quizapptesting@gmail.com"
EMAIL_PASSWORD = "practotest"
app = Celery('celerytasks', broker='pyamqp://guest@localhost//')

@app.task
def sendEmail(email_ids):
    with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        subject = 'Invitation for Practo test'
        body='You\'ve been invited to take a MCQ test. SENT ASYNCHRONOUYSLY'
        msg = f'Subject:{subject}\n\n{body}'

        for email in email_ids:
            smtp.sendmail(EMAIL_ADDRESS,email,msg)
            print("Sent email to ->",email)

    return "Done"