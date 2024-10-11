from .zettel import Zettel
from .views import zettel_bp
from .zettelkasten_topic import ZettelkastenTopic


def register_routes(app):
    app.register_blueprint(zettel_bp)


__all__ = ['Zettel','ZettelkastenTopic']
