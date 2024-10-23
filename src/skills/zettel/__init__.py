from .zettel import Zettel, LOCAL_DOCS_FOLDER
from .views import zettel_bp
from .zettelkasten_topic import ZettelkastenTopic


def register_routes(app):
    app.register_blueprint(zettel_bp)


__all__ = ['Zettel','ZettelkastenTopic', 'LOCAL_DOCS_FOLDER']
