import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret")
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"

    if FLASK_DEBUG:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///backup_manager.db'
    else:
        user = os.getenv('MYSQL_USER', 'root')
        password = os.getenv('MYSQL_PASSWORD', '')
        host = os.getenv('MYSQL_HOST', 'localhost')
        port = os.getenv('MYSQL_PORT', '3306')
        database = os.getenv('MYSQL_DATABASE', 'backup_manager')
        SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{user}:{password}@{host}:{port}/{database}?ssl_disabled=true'

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    HOST= os.getenv("HOST", "0.0.0.0")
    PORT= os.getenv("PORT", "8000")
    
    BACKUP_FOLDER = "/root/backup_files"

    DEFAULT_ADMIN_USERNAME = os.getenv('DEFAULT_ADMIN_USERNAME', 'admin')
    DEFAULT_ADMIN_PASSWORD = os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin123')
        
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', "True").lower() == "true"
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    

