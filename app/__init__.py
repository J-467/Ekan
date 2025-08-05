import os
from flask import Flask
from . import messages, db

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.instance_path, 'ekan.sqlite'),
    )

    app.register_blueprint(messages.bp)
    app.add_url_rule('/', endpoint='index')
    db.init_app(app)

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # a simple page that says hello
    @app.route('/hello')
    def hello():
        return 'Hello, World!'
    
    return app
