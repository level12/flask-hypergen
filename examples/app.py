from flask import Flask
from flask_login import LoginManager

import examples.apptemplate as apptemplate
import examples.auth as auth
import examples.classviews as classviews
import examples.commands as commands
import examples.hellocoreonly as hellocoreonly
import examples.hellohypergen as hellohypergen
import examples.index as index
import examples.inputs as inputs
import examples.partialload as partialload
from examples.sqlalchemy_counter import default_database_url
from examples.sqlalchemy_counter import make_blueprint as make_sqlalchemy_blueprint
from flask_hypergen import init_app


def create_app(testing: bool = False, database_url: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(SECRET_KEY='flask-hypergen-dev', TESTING=testing)
    init_app(app)
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def _load_user(user_id: str) -> auth.DemoUser | None:
        return auth.user_load(user_id)

    app.register_blueprint(auth.bp)
    app.register_blueprint(index.bp)
    app.register_blueprint(hellocoreonly.bp)
    app.register_blueprint(hellohypergen.bp)
    app.register_blueprint(classviews.bp)
    app.register_blueprint(inputs.bp)
    app.register_blueprint(commands.bp)
    app.register_blueprint(apptemplate.bp)
    app.register_blueprint(partialload.bp)
    app.register_blueprint(make_sqlalchemy_blueprint(database_url or default_database_url()))
    return app
