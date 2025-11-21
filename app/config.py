import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret")
    ENV = os.getenv("FLASK_ENV", "development")

    if ENV == 'development':
        SQLALCHEMY_DATABASE_URI = 'sqlite:///backup_manager.db'
    else:
        user = os.getenv('MYSQL_USER', 'root')
        password = os.getenv('MYSQL_PASSWORD', '')
        host = os.getenv('MYSQL_HOST', 'localhost')
        port = os.getenv('MYSQL_PORT', '3306')
        database = os.getenv('MYSQL_DATABASE', 'backup_manager')
        SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{user}:{password}@{host}:{port}/{database}'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    
    BACKUP_FOLDER = "/root/backup_files"

    DEFAULT_ADMIN_USERNAME = os.getenv('DEFAULT_ADMIN_USERNAME', 'admin')
    DEFAULT_ADMIN_PASSWORD = os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin123')
    
    LOGIN_MESSAGE = "Aby uzyskać dostęp, musisz się zalogować"
    
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv("GOOGLE_APP_PASSWORD")
    

