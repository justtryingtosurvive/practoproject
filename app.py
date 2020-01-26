from flask import Flask, render_template, flash, redirect, url_for, session, logging, request
from flask_mysqldb import MySQL
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
from celerytasks import sendEmail, setquestionslist, getquestionslist
import json
from redisworks import Root	


#Change this to use environment variables
EMAIL_ADDRESS = "quizapptesting@gmail.com"
EMAIL_PASSWORD = "practotest"


UPLOAD_FOLDER = 'csvfiles'
ALLOWED_EXTENSIONS = {'csv'}

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test1.db'
#Config MySQL
app.config['MYSQL_HOST'] = 'localhost'
#Use environment variables
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'password'
app.config['MYSQL_DB'] = 'quizapp'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


no_of_questions_in_test_instance = 3 

#initialize MySQL
mysql = MySQL(app)
db = SQLAlchemy(app)
tuples_list1 = []
questions_list = []
questions_to_display={}
answers_objects_list= []
question_object = []
TEST_DURATION = 2/10

class RedisDB(Root):
	pass
redis = RedisDB()

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
	email = db.Column(db.String(100))
	password = db.Column(db.String(100))
	register_date = db.Column(db.Date, default = datetime.datetime.now())

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





@app.route('/')
def index():
	return render_template('home.html')
@app.route('/about')
def about():
	return render_template('about.html')

def getCollegeList():
	result = db.session.query(College.collegename).all()

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


	
	form = RegisterForm(request.form)

	if request.method == 'POST' and form.validate():
		name = form.name.data
		email = form.email.data
		college = form.college.data
		username = form.username.data
		password = sha256_crypt.encrypt(str(form.password.data))
		student = Student(name = name, username = username, college = college, email = email, password = password)
		db.session.add(student)
		db.session.commit()
		flash('You are now registered and can log in ', 'success')
		return redirect(url_for('index'))
	
	
	return render_template('register.html', form = form )


@app.route('/adminpanel', methods = ['GET'])

def displayadminpanel():
	
	return render_template('adminpanel.html')

@app.route('/adminpanel/questiontobank', methods=['GET'])

def renderAddQuestionToBank():
	return render_template('addquestiontobank.html')

@app.route('/adminpanel/questiontobank',methods=['POST'])
def addquestiontobank():
	noofoptions = 0
	data = request.form.to_dict()
	question = data['question']
	options = []
	base_str = 'Option'
	
	
	for i in range(1,7):
		temp = base_str + str(i)
		if data[temp] != "":
			noofoptions+= 1
			options.append(data[temp])

	print("Added options ->",options)


	#Make sure noofoptions is greater than three
	#Validate that the correct option is always less than noofoptions
	
	correctoptionnumber = data['correct']
	difficulty = data['difficulty']
	
	if((int(correctoptionnumber) > noofoptions) or (noofoptions < 4)):
		flash('Check again','danger')
		return redirect(url_for('addquestiontobank'))
	quesObject = Questions(questionstring = question,correctOptionNuumber=correctoptionnumber, difficultyLevel = difficulty)
	
	
	db.session.add(quesObject)
	db.session.commit()
	newly_added_question_id = quesObject.id

	print("Newly added question Id ->>", newly_added_question_id)
	
	base_string = 'Option'
	flag_to_indicate_correct_option = False
	for i in range(1,7):
		temp = base_string + str(i)
		if i == int(correctoptionnumber):
			flag_to_indicate_correct_option = True
		if data[temp] != "":
			answer_object = Answers(answer_string= options.pop(0), question_id = newly_added_question_id, is_the_correct_answer = flag_to_indicate_correct_option)
			flag_to_indicate_correct_option = False
			db.session.add(answer_object)
			db.session.commit()

	
	
	flash('Question added ', 'success')
	
	return redirect('/adminpanel')
#Login
@app.route('/login',methods=['GET', 'POST'])
def login():
	if request.method == 'POST':
		#Get form fields
		username = request.form['username']
		password_candidate = request.form['password']
		result = Student.query.filter_by(username=username).first()
		
		if result:
			#Get stored hash
			
			password = result.password

			if sha256_crypt.verify(password_candidate, password):
				app.logger.info("Password matched")
				#Passed
				session['logged_in'] = True
				session['username'] = username
				session['status'] = 'LoggedIn'
				flash("You are now logged in ", 'success')
				
				return redirect(url_for('dashboard'))

			else:
				error = 'Invalid credentials'
				return render_template('login.html',error = error)
			cur.close()
			
		else:
			error = 'Username not found'
			return render_template('login.html',error = error)

	return render_template('login.html')


#Check if user logged in 

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
	redis.questions.to.display = None
	redis.questions.list = None
	if session['status'] == 'InTest':
		session.clear()
		flash("This action is not allowed. Logging out.", 'danger')
		return redirect(url_for('login'))
	elif session['status'] == 'done':
		session.clear()
		flash("Test sucessfully submitted. Logging out",'Success')
		return redirect(url_for('login'))
	else:
		session.clear()
		flash("You are now logged out", 'success')
		return redirect(url_for('login'))

@app.route('/dashboard')
@is_logged_in
def dashboard():
	if session['status'] == 'InTest':
		print("Invalid action. Logging out")
		return redirect((url_for('logout')))
	return render_template('dashboard.html')


@app.route('/adminpanel/createtest',methods=['GET','POST'])

def createtest():
	if(request.method =='GET'):
		questions = Questions.query.all()
		return render_template('createtest.html', questions=questions)
	else:
		college = request.form.get("college")
		added_questions = []
		question_ids = db.session.query(Questions.id).all()
		question_id_list = [i[0] for i in question_ids]
		question_id_list_strings = [str(i) for i in question_id_list]
		for question_id in question_id_list_strings:
			if request.form.get(question_id,"off") == 'on':
				added_questions.append(int(question_id))
		
		collegeList = db.session.query(College.collegename).all()
		collegeList = [i[0] for i in collegeList]


		if college not in collegeList:
			collegeInstance = College(collegename = college)
			db.session.add(collegeInstance)
			db.session.commit()


		testcreated = Test(collegename=college)
		db.session.add(testcreated)
		db.session.commit()


		test_created_id = testcreated.test_id
		for question in added_questions:

			test_question_instance = Test_Question(test_id=test_created_id, question_id=question)
			db.session.add(test_question_instance)
			db.session.commit()


		msg = "Added questions "+ str(added_questions) + "for " + college 
		flash(msg,'success')
		
		return redirect(url_for('displayadminpanel'))
		




def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/adminpanel/sendinvites',methods=['GET','POST'])
def sendinvites():
	if request.method == 'GET':
		tests = Test.query.all()
		return render_template('sendinvites.html', tests=tests)
	else:
		# check if the post request has the file part
		if 'file' not in request.files:
			flash('No file part')
			return redirect(request.url)
		file = request.files['file']
		# if user does not select file, browser also
		# submit an empty part without filename
		if file.filename == '':
			flash('No selected file','danger')
			return redirect(request.url)
		if file and allowed_file(file.filename):
			filename = secure_filename(file.filename)
			file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
			df = pd.read_csv(os.path.join(app.config['UPLOAD_FOLDER'], filename))
			emails = df.values[:,0] #List of emails from the file
			
			selectedtestid = request.form.get('selectedtestid')
			print("selectedtestid => ", selectedtestid)
			''' Create a test instance for each email_id. Select some random questions from Test_question. '''
			

			#Fetch all the questions which belong to a particular test
			questions = Test_Question.query.filter_by(test_id = selectedtestid).all()
			print("Questions which belong to test id number",selectedtestid,"->>",questions)

			for email in emails:
				#Pick any no_of_questions_in_test_instance number of questions randmomly from Test_question
				RandomListOfQuestions = random.sample(questions, 3)
				print("For email id = ",email,"Selected questions are->>",RandomListOfQuestions)

				for row in RandomListOfQuestions:
					test_question_id_of_random_question = row.test_question_id
					test_instance_object = TestInstance(student_email = email, test_question_id = test_question_id_of_random_question)
					db.session.add(test_instance_object)
					db.session.commit()
		
			sendEmail.delay(list(emails))
			flash("Invites sent!", 'success')


			
			return redirect(url_for('displayadminpanel'))
		print("Should be flashing")
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
		redis.questions.list = questions_list
	
		#So we now save the question_ids of the questions to be displayed in a global dictionary,
		#Whose indices start from 1. This is because we want to use the request parameter recieved
		#To get the question_id of the question to be displayed

		global questions_to_display
		
		for i in range(1,len(questions_list)+1):
			questions_to_display[i] = questions_list[i-1]
		
		redis.questions.to.display = questions_to_display
		print("questions_to_display-->>", questions_to_display)

		ts = datetime.datetime.now().timestamp()  
		'''Get current timestamp, this returns in seconds. But client side Javascript uses miliseconds. So, multiply by 1000'''
		redis.ts = ts
		#This is basically the timestamp of the start of the test		
		return redirect(('/question/1'))
		


@app.route('/question/<number>', methods=['GET','POST'])  #This 'number' refers to the question number 
#which will be displayed on the screen to the user i.e. the question number in a particular test for a user.
@is_logged_in

def displayquestion(number):
	session['status'] = 'InTest'
	
	if request.method == 'GET' and request.args.get('selectedanswer')== None:
			
			
			if int(number) == 0:
				return redirect('/question/1')
			if int(number) <= no_of_questions_in_test_instance:
				question_to_be_displayed = questions_to_display.get(int(number))
				if question_to_be_displayed == None:
					return "No questions for you "

				global question_object #This is to communicate with the part that handles the POST request
				#OTherwise, we would have to query again
				
				print("Question to be displayed ->>",question_to_be_displayed)
				question_object = Questions.query.filter_by(id=question_to_be_displayed).all()
				#The above query returns a list. The list will contain only one element, which is an object of
				#Question class. We just need the object, so that we can pass the object to the render_template method.
				session['current_question_id'] = question_to_be_displayed
				print("Question_object->",question_object[0])
				question_object = question_object[0]

				#We now need to just query the answers table to fetch the options available for the question_id
				global answers_objects_list #This is to communicate with the part that handles the POST request.
				answers_objects_list = Answers.query.filter_by(question_id = question_to_be_displayed).all()
				print("Answers objects list ->>", answers_objects_list)

				#Use redis here
				ts = redis.ts

				ts = ts*1000
				endtime = ts+ TEST_DURATION*1000*60
				redis.end.time = endtime
		

				
				return render_template('questiondisplay.html',question=question_object, question_number = int(number),answers = answers_objects_list,total_number_of_questions_in_test=no_of_questions_in_test_instance, endtime=endtime)

			else:
				return render_template("confirmendtest.html",question_number=int(number))
	
	else:

	
		''' Basically, I need to add one more column,correct_answer_selected to testinstance, and rebuild the database. 
		Make it false by default. Get the list of TestInstance objects, filtered by email_id of the session. 
		Then, if the correct answer is marked for the question we just displayed, change the correct_answer_selected to true. '''
		
		print("Session variable of qid->>", session['current_question_id'])

		test_instance_list_of_tuples = TestInstance.query.join(Test_Question, Test_Question.test_question_id ==  TestInstance.test_question_id).add_columns(Test_Question.question_id, Test_Question.test_id,TestInstance.test_instance_id,TestInstance.student_email).filter(TestInstance.student_email == session['email_id']).all()
		#The above query results in a list of tuples, of the format (<TestInstance object>, selected columns). 
		#We just want the TestInstance objects, so that we can modify their correct_answer_selected column
		
		print("Test instance list of tuples in display questions ->>", test_instance_list_of_tuples)
		
		
		
		for row in test_instance_list_of_tuples:
			if row[1] == session['current_question_id']:
				test_instance_associated_with_question = row[0]

		print("test_instance_associated_with_question -->>", test_instance_associated_with_question)

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

	




@app.route('/adminpanel/viewtests')
def viewtests():
	return render_template("viewtests.html")

@app.route('/endtest', methods = ['POST','GET'])
def endtest():
	session['status'] = 'done'
	return redirect('/logout')






if __name__ == '__main__':
	app.secret_key='secret123'
	app.run(debug = True)
#Hey