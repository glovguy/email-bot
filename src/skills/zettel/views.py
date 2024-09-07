from flask import Blueprint, request
from flask import request
from .zettel import Zettel


zettel_bp = Blueprint('zettel', __name__, url_prefix='/zettel')

@zettel_bp.route('/')
def zettel_home():
    zettels = Zettel.query.all() # TODO: scope by user

    zettel_info = []
    for ztl in zettels:
        zettel_info.append(render_zettel(ztl))
    top_nav = "<h1>Zettel</h1><div><a href=\"/zettel/semantic_search/\">Semantic Search</a></div><br><hr>"
    return top_nav + "<div>" + "</div><hr><div>".join(zettel_info) + "</div>"

@zettel_bp.route('/semantic_search/')
def semantic_search():
    search_query = request.args.get('search_query')
    top_nav = f"""
    <h1>Zettel</h1>
    <div><a href=\"/zettel/\">back</a></div><br>
    <form action="{request.full_path}" method="GET">
        <input type="text" name="search_query" placeholder="Enter your search query">
        <input type="submit" value="Search">
    </form>
    <br>
    """
    if not search_query:
        return top_nav

    search_results = Zettel.find_similar(search_query, limit=20)
    results_string = "<div>" + "</div><hr><div>".join(
        [f"<i>sim score:</i> {res[1]}<br>{render_zettel(res[0])}" for res in search_results]
    ) + "</div>"

    return top_nav + f"<h3>Search results</h3>search query:<br><pre style=\"background-color: lightgrey;\">{search_query}</pre><hr>" + results_string

def render_zettel(ztl):
    return f"<strong>[[{ztl.title}]]</strong><br>uuid: {ztl.uuid}, updated_at: {ztl.updated_at}<br>{ztl.content}"
