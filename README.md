# Quiz App
A web application to take quiz specially for a placement drive.The registered candidates will get an email with a link to register.After registration,they can login to take the quiz with registered mail id.

## Information

### Requirements

The requirements for the application can be found [in the drive link, here](https://docs.google.com/document/d/1e0ACrY5O1brUFhx5Dj6SN5YBcXShyoyD4OOHvOBqZkA/edit)

### ER Diagram

You can find the er diagram here!!

[ER Diagram](https://github.com/MariyaBosy/practoproject/blob/master/erdiagram.pdf)

### API Documentation

The API documentation can be found [here on Apiary](https://documenter.getpostman.com/view/10029778/SWTA9xji).

### Tools and Tech

1. Python version 3.x
2. Flask
3. Jinja
4. SQLite
5. SQLAlchemy
6. Redis
7. Celery
8. JQuery
9. Ajax
10. Git
11. EC2

## Usage

### Requirements

The requirements can be downloaded from :(https://github.com/justtryingtosurvive/practoproject/blob/master/requirements.txt)

1. Python
2. SQLite
3. Celery
4. Rabbitmq
5. Flask


### How to run
1. Install all requirements using pip3 install -r requirements.txt
2. Open a interactive python shell and type in "from app import db; db.create_all()" This will create the database on the server
3. Start a RabbitMQ server by executing "sudo service rabbitmq-server start" on the terminal
4. Start a Celery worker by executing "celery -A celerytasks worker --loglevel=info" on the terminal. 
5. Execute the app.py by executing "python3 app.py"


