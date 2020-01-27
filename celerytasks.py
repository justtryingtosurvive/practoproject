from celery import Celery
from flask import Flask, render_template, flash, redirect, url_for, session, logging, request

import smtplib
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey

EMAIL_ADDRESS = "quizapptesting@gmail.com"
EMAIL_PASSWORD = "practotest"
app = Celery('celerytasks', broker='pyamqp://guest@localhost//')
saved_list = []




@app.task
def sendEmails(email_ids):
    with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        subject = 'Invitation for Practo test'
        body='''You\'ve been invited to take an MCQ test! Please click on the below link. Register on the site
        with this email ID, and pick a username for the same. After registering, login with the username and password.
        Then, you will be able to take the test. 
        Please click here: http://13.233.250.169/ ''' 


        msg = f'Subject:{subject}\n\n{body}'

        for email in email_ids:
            smtp.sendmail(EMAIL_ADDRESS,email,msg)

            print("Sent email to ->",email)




    return "Done"


@app.task

def setquestionslist(somelist):
    saved_list = somelist
    print("Saved list ->", saved_list)
    return "saved"


@app.task
def getquestionslist():
    print("Returned list->", saved_list)
    return saved_list
