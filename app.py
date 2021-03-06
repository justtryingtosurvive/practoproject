from flask import Flask, render_template, flash, redirect, url_for, session, logging, request, send_file, send_from_directory
from wtforms import Form, StringField, TextAreaField, PasswordField, validators, SelectField
from passlib.hash import sha256_crypt

from flask_sqlalchemy import SQLAlchemy
#from sqlalchemy import ForeignKey
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, backref
import datetime
from functools import wraps
import pandas as pd
import csv
import os
from werkzeug.utils import secure_filename
import smtplib
import os
import random
from celerytasks import sendEmails, setquestionslist, getquestionslist
import json



#Change this to use environment variables

UPLOAD_FOLDER = 'csvfiles'    #Upload folder is the folder name on the server which will store the uploaded 
ALLOWED_EXTENSIONS = {'csv'}  #Csv files. Allowed extensions is the list of allowed extensions of the file
#Which was uploaded

app = Flask(__name__)
app.secret_key='secret123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test1.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False           #Ignore the warnings
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


no_of_questions_in_test_instance = 10      #Lets say the number of questions each student gets is 10


db = SQLAlchemy(app)
#These are some global variables which are used to help different routes pass information amongst themselves.
#We should have used redis for this purpose but we couldn't get it to work properly
#The uses of all these will make sense when they are actually being used
tuples_list1 = []
questions_list = []
questions_to_display={}
answers_objects_list= []
question_object = []
TEST_DURATION = 20   #This is in minutes
selected_answer_id = 0
ts=0
endtime=0
answer_selected_list={}


#Declare the classes or tables in our DB

class Test(db.Model):
	__tablename__ = 'test'
	test_id = db.Column(db.Integer, primary_key=True)
	collegename = db.Column(db.String(100), ForeignKey("college.collegename"), nullable=False)


class Test_Question(db.Model):
	__tablename__ = 'test_question'
	test_question_id = db.Column(db.Integer, primary_key=True)
	test_id = db.Column(db.Integer, ForeignKey("test.test_id"), nullable=False)
	question_id = db.Column(db.Integer, ForeignKey("questions.id"), nullable=False)



class TestInstance(db.Model):
	__tablename__ = 'testinstance'
	test_instance_id = db.Column(db.Integer, primary_key=True)
	test_question_id = db.Column(db.Integer, ForeignKey("test_question.test_question_id"), nullable=False)
	student_email = db.Column(db.String(400), nullable=False)
	correct_answer_selected = db.Column(db.Boolean, default = False)



class Student(db.Model):
	__tablename__ ='student'
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(100))
	username = db.Column(db.String(100))
	college = db.Column(db.String(100), ForeignKey("college.collegename"), nullable=False)
	email = db.Column(db.String(100),unique=True)
	password = db.Column(db.String(100))
	register_date = db.Column(db.Date, default = datetime.datetime.now())
	score = db.Column(db.Integer)

class College(db.Model):
	__tablename__ ='college'
	id = db.Column(db.Integer, primary_key = True)
	collegename = db.Column(db.String(400),unique=True)
	students = db.relationship('Student', lazy=True)
	tests = db.relationship('Test', lazy=True)

class Questions(db.Model):
	__tablename__ ='questions'
	id = db.Column(db.Integer, primary_key=True)
	questionstring = db.Column(db.String(400))
	correctOptionNuumber = db.Column(db.Integer)
	difficultyLevel = db.Column(db.Integer)

class Answers(db.Model):
	__tablename__ = 'answers'
	answer_id = db.Column(db.Integer, primary_key=True)
	answer_string = db.Column(db.String, nullable=False)
	question_id = db.Column(db.Integer, ForeignKey('questions.id'), nullable = False)
	is_the_correct_answer = db.Column(db.Boolean, default=False)

class InvitedEmails(db.Model):
	__tablename__ = 'invitedemails'
	invite_id = db.Column(db.Integer, primary_key=True)
	email_id = db.Column(db.String)


#Basically, returns the homepage
@app.route('/')
def index():
	return render_template('home.html')

#Basically, returns the about page. 
@app.route('/about')
def about():
	return render_template('about.html')


#This method is used to get the list of colleges for which a test has been created, so that only 
#the students from those colleges can register for which a test has been created 
def getCollegeList():
	result = db.session.query(College.collegename).all()  
	#We need it to be in this format, i.e, (collegename, collegename) because the WTForms method which 
	#We use to render the field expects it to be in this format. First value is the value which will be displayed
	#The other is the value which be assigned to the input field
	#We use list comprehension to turn the array into the above format
	tuples_list = [(i[0],i) for i in result]
	
	return  tuples_list


#WT Forms wala form
@app.route('/register', methods = ['GET', 'POST'])
def register():
	tuples_list1 = getCollegeList()
	class RegisterForm(Form):
		name = StringField('Name', [validators.Length(min=1, max=50)])
		username = StringField('Username', [validators.Length(min=4, max = 25)])
		college = SelectField('College', choices=tuples_list1)
		email = StringField('Email', [validators.Length(min=6, max=50)])
		password = PasswordField('Password', [
				validators.DataRequired(),
				validators.EqualTo('confirm', message = 'Passwords do not match')

				])
		confirm = PasswordField('Confirm Password')

	#This is a really expensive way to do things, but what we are essentially doing is that creating a new 
	# RegisterForm class every time a student tries to register. This is because we need to know what are the
	# Colleges for which a test has been created. 
	# 	
	form = RegisterForm(request.form)

	if request.method == 'POST' and form.validate():
		name = form.name.data
		email = form.email.data
		college = form.college.data
		username = form.username.data
		password = sha256_crypt.encrypt(str(form.password.data))
		#We encrypt the password we recieved
		student = Student(name = name, username = username, college = college, email = email, password = password)
		db.session.add(student)
		db.session.commit()
		flash('You are now registered and can log in ', 'success')
		return redirect(url_for('index'))
		#We basically send the user back to the homepage after registering
	
	#If he just wants to GET the form to fill it, we render the template with the form we created and send it

	return render_template('register.html', form = form )

#This is to prevent people from accessing the login page. 
#Not very safe but it will do. I am assuming there is only one admin, whose credentials are hardcoded.
@app.route('/adminpanellogin', methods=['GET','POST'])
def displayadminlogin():
	if request.method == 'POST':
		admin_username = "root"
		admin_password = "helloworld"
		entered_username = request.form.get('admin_username')
		entered_password = request.form.get('admin_password')
		if entered_username == admin_username and entered_password == admin_password:
			flash('Successfully logged in ', 'success')
			return redirect(url_for('displayadminpanel'))
		else:
			flash('Invalid credentials, check again','danger')
			return redirect('/')
	else:
		return render_template('adminpanellogin.html')



@app.route('/adminpanel', methods = ['GET'])
def displayadminpanel():
	#Nothing much to do, just render the page and send it back
	return render_template('adminpanel.html')

@app.route('/adminpanel/questiontobank', methods=['GET'])
def renderAddQuestionToBank():
	#Again, just render a page and send it to the user. 
	return render_template('addquestiontobank.html')

@app.route('/adminpanel/questiontobank',methods=['POST'])
def addquestiontobank():
	noofoptions = 0              #The number of options the user selected there
	data = request.form.to_dict() #Convert the form data into a dict for easier processing
	question = data['question']
	options = []                 #This will contain the strings of the options entered
	base_str = 'Option'          #This is the base string which will make it easier to iterate through the 
								#keys of the data dict. 
	
	
	for i in range(1,7):       #Since there are 6 option fields rendered.
		temp = base_str + str(i)
		if data[temp] != "":
			noofoptions+= 1
			options.append(data[temp]) #Basically, we check whether a field is empty or not. If it is not, we append
			#to the list

	print("Added options ->",options)


	#Make sure noofoptions is greater than three
	#Validate that the correct option is always less than noofoptions
	
	correctoptionnumber = data['correct']  #get the selected option number which is supposed to be the correct
	#option

	difficulty = data['difficulty'] #Get the difficulty level of the question
	
	if((int(correctoptionnumber) > noofoptions) or (noofoptions < 4)):  #If any of the validations mentioned aren't true
		flash('Check again','danger')
		return redirect(url_for('addquestiontobank'))
	quesObject = Questions(questionstring = question,correctOptionNuumber=correctoptionnumber, difficultyLevel = difficulty)
	#Everything looks okay, we can add a row in the Questions table. 
	
	db.session.add(quesObject)
	db.session.commit()
	
	newly_added_question_id = quesObject.id   #We need to get the ID of the newly added question, so that 
	#we can use it to map the answers/options/whatever you call it to the question

	print("Newly added question Id ->>", newly_added_question_id)
	
	base_string = 'Option'    #Same use as mentioned above, to make it easier to iterate through the options

	flag_to_indicate_correct_option = False   #Basically, set the boolean is_the_correct_answer to either true 
	#or false, based on the provided correct option number. 
	for i in range(1,7):
		temp = base_string + str(i)
		if i == int(correctoptionnumber):
			flag_to_indicate_correct_option = True
		if data[temp] != "":
			answer_object = Answers(answer_string= options.pop(0), question_id = newly_added_question_id, is_the_correct_answer = flag_to_indicate_correct_option)
			flag_to_indicate_correct_option = False
			db.session.add(answer_object)
			db.session.commit()
			#Add the options to the answers table, but only if they are not empty strings. 

	
	
	flash('Question added ', 'success')
	
	return redirect('/adminpanel')


@app.route('/login',methods=['GET', 'POST'])
def login():
	if('logged_in' in session):
		return redirect(url_for('dashboard')) #The user is logged in, but he still wants to access the login
		#page. So lets just send him back to dashboard. 
	if request.method == 'POST':
		#Handle the form data the user has POSTed to us. 
		username = request.form['username']
		password_candidate = request.form['password']  #This is the password the user has entered.
		result = Student.query.filter_by(username=username).first()
		
		if result:
			#Get stored hash
			#This is the value we've stored in the DB
			password = result.password

			if sha256_crypt.verify(password_candidate, password):
				app.logger.info("Password matched")
				#Passed
				session['logged_in'] = True    #Set session variables for later use. 
				session['username'] = username
				session['status'] = 'LoggedIn'
				flash("You are now logged in ", 'success')
				
				return redirect(url_for('dashboard')) #Send him back to the login page

			else:
				error = 'Invalid credentials'
				return render_template('login.html',error = error) #just flash a message saying auth failed

			
		else:
			error = 'Username not found'   #If the query resulted in no rows, then no username was found
			return render_template('login.html',error = error)

	return render_template('login.html')  #The user wants the Login page, so give it to him 


#Check if user logged in 
#Okay so this part of code is something even I dont uderstand. This was from the flask 
#Documentation. Basically, we use @is_logged_in after every route to make sure the route only
#processes requests if the user is logged in. Otherwise it'll just send a message and ask him to login
def is_logged_in(f):
	@wraps(f)
	def wrap(*args, **kwargs):
		if 'logged_in' in session:
			return f(*args, **kwargs)
		else:
			flash('Unauthorized, please log in ', 'danger')
			return redirect(url_for('login'))

	return wrap

@app.route('/logout')
def logout():
	
	tuples_list1 = []
	questions_list = []
	questions_to_display={}
	answers_objects_list= []
	question_object = []
	answer_selected_list={}
	#Clear every global variable we've used.

	if session['status'] == 'InTest':
		session.clear()
		flash("This action is not allowed. Logging out.", 'danger')
		return redirect(url_for('login'))
		#The user did something he wasn't supposed to
	elif session['status'] == 'done':
		session.clear()
		flash("Test sucessfully submitted. Logging out",'Success')
		return redirect(url_for('login'))
		#The user completed the test 
	else:
		session.clear()
		flash("You are now logged out", 'success')
		return redirect(url_for('login'))
		#He clicked on logout on the dashboard

@app.route('/dashboard')
@is_logged_in
def dashboard():
	if session['status'] == 'InTest':
		print("Invalid action. Logging out") #If he's in the test but tries to come to the dashboard again,
		#we log the bad boy out
		return redirect((url_for('logout')))
	return render_template('dashboard.html') #Otherwise, we just give him the dashboard 


@app.route('/adminpanel/createtest',methods=['GET','POST'])

def createtest():
	if(request.method =='GET'):
		questions = Questions.query.all() #Send all the questions to the client, render everything
		#On the client side 

		return render_template('createtest.html', questions=questions)
	else:
		college = request.form.get("college")
		added_questions = []
		question_ids = db.session.query(Questions.id).all()
		question_id_list = [i[0] for i in question_ids]  #The query returns a weird format, use list
		#comprehension to make it into a normal list

		question_id_list_strings = [str(i) for i in question_id_list]
		#Convert the list of ints to strings


		for question_id in question_id_list_strings:
			if request.form.get(question_id,"off") == 'on':
				added_questions.append(int(question_id))
		#The get method on a python will return the default if there is no key, instead of throwing an error
		#Which can come in really handy. 
		
		#Get the list of all the colleges and sanitize them
		collegeList = db.session.query(College.collegename).all()
		collegeList = [i[0] for i in collegeList]

		#Only add the colleges if its not already added to the colleges tables
		if college not in collegeList:
			collegeInstance = College(collegename = college)
			db.session.add(collegeInstance)
			db.session.commit()

		#Create a new test object/row for this college. It is basically a one to one mapping
		testcreated = Test(collegename=college)
		db.session.add(testcreated)
		db.session.commit()

		#Add all questions to the Test_question table. This is basically a table which has a mapping
		#from Questions and Test. Basically, each Test can have multiple questions in it...

		test_created_id = testcreated.test_id
		for question in added_questions:
			test_question_instance = Test_Question(test_id=test_created_id, question_id=question)
			db.session.add(test_question_instance)
			db.session.commit()

		#Nothing special, move along

		msg = "Added questions "+ str(added_questions) + "for " + college 
		flash(msg,'success')
		
		return redirect(url_for('displayadminpanel'))




def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
		   #Basically, see if the filename is allowed or not. That is, check if the part after 
		   #The . is a list in ALLOWED_EXTENSIONS. which just contains 'csv'

@app.route('/adminpanel/sendinvites',methods=['GET','POST'])
def sendinvites():
	if request.method == 'GET':
		tests = Test.query.all()
		return render_template('sendinvites.html', tests=tests)
		#just send all the rows of the tests to the render_template method which will put everything in place

	else:
		# check if the post request has the file part
		if 'file' not in request.files:
			flash('No file part','danger')
			return redirect(request.url)
		
		file = request.files['file']
		# if user does not select file, browser also
		# submit an empty part without filename
		if file.filename == '':
			flash('No selected file','danger')
			return redirect(request.url)
		if file and allowed_file(file.filename):
			filename = secure_filename(file.filename) #Secure filename is something I dont understand
			file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename)) #Save the file in the UPLOAD FOLDER thing

			df = pd.read_csv(os.path.join(app.config['UPLOAD_FOLDER'], filename)) #Read the CSV file we just got
			emails = df.values[:,0] #List of emails from the file #I am assuming the csv just contains a list of 
			#Emails in the first row
			
			selectedtestid = request.form.get('selectedtestid') #The admin will have selected a test, whose test id we
			#will get

			print("selectedtestid => ", selectedtestid)
			''' Create a test instance for each email_id. Select some random questions from Test_question. '''
			

			#Fetch all the questions which belong to a particular test
			questions = Test_Question.query.filter_by(test_id = selectedtestid).all()
			print("Questions which belong to test id number",selectedtestid,"->>",questions)

			#All the rows of the invitedemails table
			invitedemails = db.session.query(InvitedEmails.email_id).all()
			print("Invited emails =>",invitedemails)
			
			#The query will result in a list of tuples, but we only really need the first element of each tuple

			invitedemailslist = []
			for invitedemail in invitedemails:
				invitedemailslist.append(invitedemail[0])

			for email in emails:
				if email not in invitedemailslist:
					#Pick any no_of_questions_in_test_instance number of questions randmomly from Test_question
					RandomListOfQuestions = random.sample(questions, no_of_questions_in_test_instance)
					print("For email id = ",email,"Selected questions are->>",RandomListOfQuestions)


					for row in RandomListOfQuestions:
						test_question_id_of_random_question = row.test_question_id  
						#Use the question_id of the randomly picked question to create a test_instance row, 
						#Which can then be committed. Basically, we just create test instance rows for every
						#Email ID

						test_instance_object = TestInstance(student_email = email, test_question_id = test_question_id_of_random_question)
						db.session.add(test_instance_object)
						db.session.commit()
					
				#We add the email ID we just created instances for in our invitedEmails table, so that 
				#We can avoid sending duplicate emails. So, we basically say each student can take only
				#One test

					invited_email_instance = InvitedEmails(email_id = email)
					db.session.add(invited_email_instance)
					db.session.commit()
			
			#Send the list of emails to the Celery worker, because sending Emails using an SMTP
			#server is really expensive. We dont really care whether the email is valid or not. 
			#We attempt to send emails


			sendEmails.delay(list(emails))
			flash("Invites sent!", 'success')

			return redirect(url_for('displayadminpanel'))
		
		flash("Please check the file uplaoded and try again", 'danger')
		return redirect(url_for('displayadminpanel'))



@app.route('/startquiz/<session_username>')
@is_logged_in
def starttest(session_username):
	if(session['username'] == session_username):
		''' Fetch questions for this username, send those questions.   '''
		student_associated_with_logged_in_username = Student.query.filter_by(username=session_username).one()
		email_associated_with_logged_in_student = student_associated_with_logged_in_username.email
		session['email_id'] = email_associated_with_logged_in_student
		questions_associated_with_email=[]
		#We basically fetched the email_id of the logged in user. Now we need to query the Test_instance
		#table to find the questions which are associated with this email. 

		#We join the Test_Question table and the TestInstance table on question_id, and then
		#Select the rows for which the email_id is the same as the email_associated_with_logged_in_student

		test_question_list = Test_Question.query.join(TestInstance, Test_Question.test_question_id ==  TestInstance.test_question_id).add_columns(Test_Question.question_id, Test_Question.test_id,TestInstance.test_instance_id,TestInstance.student_email).filter(TestInstance.student_email == email_associated_with_logged_in_student).all()
		print("joined table ->>", test_question_list)
		print("\n")
		
		#The above join query returns a table with multiple columns, but we dont really need all the columns.
		#Hence, we just select the question_id column from the table. This is the second element of each tuple
		#in the list, hence the below operations. 

		for iterator in test_question_list:
			print("iterator->>",iterator)
			print("questions->>",iterator[1])
			questions_associated_with_email.append(iterator[1])


		#Hence, questions_associated_with_email contains the question_ids which are meant for the email address
		#which was used to sign in. 
		print("questions_associated_with_email ->>", questions_associated_with_email)
		
		#We now save this in a global variable questions_list. We pop a question_id from this list
		#and display the question accordingly in another route.
		global questions_list
		questions_list = questions_associated_with_email
		
	
		#So we now save the question_ids of the questions to be displayed in a global dictionary,
		#Whose indices start from 1. This is because we want to use the request parameter recieved
		#To get the question_id of the question to be displayed

		global questions_to_display
		
		for i in range(1,len(questions_list)+1):
			questions_to_display[i] = questions_list[i-1]
		
		
		global ts, endtime

		print("questions_to_display-->>", questions_to_display)

		ts = datetime.datetime.now().timestamp()  
		'''Get current timestamp, this returns in seconds. But client side Javascript uses miliseconds. So, multiply by 1000'''
		
		ts = ts*1000
		endtime = ts+ TEST_DURATION*1000*60
		#This is basically the timestamp of the end of the test		
		
		
		return redirect(('/question/1'))
		


@app.route('/question/<number>', methods=['GET','POST'])  #This 'number' refers to the question number 
#which will be displayed on the screen to the user i.e. the question number in a particular test for a user.
@is_logged_in

def displayquestion(number):
	session['status'] = 'InTest'
	
	if request.method == 'GET' and request.args.get('selectedanswer')== None:
			
			#So he tries to access the 0th question, which doesn't exist. So we just send him back to
			#the first question
			if int(number) == 0:
				return redirect('/question/1')
			if int(number) <= no_of_questions_in_test_instance:  #If there are still questions to be displayed

				question_to_be_displayed = questions_to_display.get(int(number))
				
				if question_to_be_displayed == None: #If there are no questions for this user
					return render_template("Noquestions.html")

				global question_object #This is to communicate with the part that handles the POST request
				#OTherwise, we would have to query again
				
				print("Question to be displayed ->>",question_to_be_displayed)
				question_object = Questions.query.filter_by(id=question_to_be_displayed).all()
				#The above query returns a list. The list will contain only one element, which is an object of
				#Question class. We just need the object, so that we can pass the object to the render_template method.
				session['current_question_id'] = question_to_be_displayed
				
				question_object = question_object[0]

				#We now need to just query the answers table to fetch the options available for the question_id
				global answers_objects_list #This is to communicate with the part that handles the POST request.
				answers_objects_list = Answers.query.filter_by(question_id = question_to_be_displayed).all()
				
				global ts, endtime, answer_selected_list
		
				global selected_answer_id
				global answer_selected_list
				
				return render_template('questiondisplay.html',question=question_object, question_number = int(number),answers = answers_objects_list,total_number_of_questions_in_test=no_of_questions_in_test_instance, endtime=endtime, selected_answer_id = answer_selected_list.get(session.get('current_question_id')))

			else:
				return render_template("confirmendtest.html",question_number=int(number))
	
	else:
		
	
		''' Basically, I need to add one more column,correct_answer_selected to testinstance, and rebuild the database. 
		Make it false by default. Get the list of TestInstance objects, filtered by email_id of the session. 
		Then, if the correct answer is marked for the question we just displayed, change the correct_answer_selected to true. '''
		
		

		test_instance_list_of_tuples = TestInstance.query.join(Test_Question, Test_Question.test_question_id ==  TestInstance.test_question_id).add_columns(Test_Question.question_id, Test_Question.test_id,TestInstance.test_instance_id,TestInstance.student_email).filter(TestInstance.student_email == session['email_id']).all()
		#The above query results in a list of tuples, of the format (<TestInstance object>, selected columns). 
		#We just want the TestInstance objects, so that we can modify their correct_answer_selected column
		
		for row in test_instance_list_of_tuples:
			if row[1] == session['current_question_id']:
				test_instance_associated_with_question = row[0]

		#Now, we need to check whether the correct answer for this question is checked or not. 
		#So, we need to get the answer ID of the correct answer. Then we check whether the checkbox
		#Associated with that answer ID is checked or not. If its checked, its a correct answer. 
		#If not, its the wrong answer. 
		correct_answer_id = 0
		for answer_object in answers_objects_list:
			
			if answer_object.is_the_correct_answer:
				correct_answer_id = answer_object.answer_id
		print("Correct answer ID ->",correct_answer_id)

		#Now, we have the correct answer ID for the question. We check to see if the checkbox is marked

		selected_answer_id = request.args.get('selectedanswer',0,type=int)
		answer_selected_list[session['current_question_id']] = selected_answer_id
		
		print("Selected answer ID ->", selected_answer_id)
		try:
			if int(selected_answer_id) == correct_answer_id:
				print("Correct answer picked")
				test_instance_associated_with_question.correct_answer_selected = True
				db.session.commit()
			else:
				print("Wrong answer picked")
				if test_instance_associated_with_question.correct_answer_selected == True:
					test_instance_associated_with_question.correct_answer_selected = False
					db.session.commit()
		except TypeError:
			print("No answer was selected")

		print("request_url-->>",request.url)
		return ('', 204)

	







@app.route('/endtest', methods = ['POST','GET'])
def endtest():
	session['status'] = 'done'
	#Calculate the score here. 
	
	email_associated_with_logged_in_student = session['email_id']
	student_associated_with_logged_in_username = Student.query.filter_by(username=session['username']).one()
	test_instance_list_of_tuples = TestInstance.query.join(Test_Question, Test_Question.test_question_id ==  TestInstance.test_question_id).add_columns(Test_Question.question_id, Test_Question.test_id,TestInstance.test_instance_id,TestInstance.student_email).filter(TestInstance.student_email == session['email_id']).all()
	print("test_instance_list_of_tuples", test_instance_list_of_tuples)
	score = 0
	test_instance_object_list = []
	list_of_question_ids_for_this_student = []
	for row in test_instance_list_of_tuples:
		test_instance_object_list.append(row[0])
		list_of_question_ids_for_this_student.append(row[1])
	print("test_instance_object_list-->>",test_instance_object_list)
	print(" list_of_question_ids_for_this_student ->>",list_of_question_ids_for_this_student)
	for i in range(0,len(test_instance_object_list)):
		question_object = Questions.query.filter_by(id = list_of_question_ids_for_this_student[i]).one()
		difficulty_level_of_question = question_object.difficultyLevel
		if test_instance_object_list[i].correct_answer_selected:
			score = score + difficulty_level_of_question
	print("Score ->>",score)

	student_associated_with_logged_in_username.score = score
	db.session.commit()




	return redirect('/logout')



@app.route('/adminpanel/testresults',methods=['POST','GET'])
def viewtestresults():
	if request.method == 'GET':
		test_objects = Test.query.all()
		return render_template('testresults.html',tests=test_objects)
	else:
		selected_test_id = request.form.get("selectedtest")
		

		joined_table = Student.query.join(Test, Student.college == Test.collegename).add_columns(Student.college, Test.collegename, Student.email, Student.score).filter(Test.test_id == selected_test_id).all()
		
		student_list = []
		scores_list = []
		for row in joined_table:
			student_list.append(row[0])
			scores_list.append(row[4])
		
		merged_list = [(student_list[i].name, student_list[i].email, scores_list[i]) for i in range(0, len(student_list))] 
		
		#Basically, merge the two lists into a single list of tuples, so that its easier to sort 
		
		sorted_list = merged_list.sort(key= lambda x:x[2], reverse=True) #Sorts the list of tuples based on
		#the third element of each tuple, in descending order
		sorted_list = merged_list
		print("Sorted list->", sorted_list )

		test_object = Test.query.filter_by(test_id = selected_test_id).one()
		test_name = test_object.collegename 
		filename_to_send = test_name
		filename_to_send = filename_to_send+'.csv'
		print("name of file->",filename_to_send)

		with open(filename_to_send, 'w', newline="") as file:
			writer = csv.writer(file)
			writer.writerow(['Name','EmailID','Score'])
			writer.writerows(sorted_list)
		





		return send_file(os.getcwd()+'/'+filename_to_send,as_attachment=True, attachment_filename=filename_to_send)



if __name__ == '__main__':
	
	app.run(debug = True, host="0.0.0.0", port=80)
#Hey