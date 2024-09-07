from flask import Blueprint, request
from flask import request
from .zettel import Zettel


zettel_bp = Blueprint('zettel', __name__, url_prefix='/zettel')

@zettel_bp.route('/')
def zettel_home():
    zettels = Zettel.query.all() # TODO: scope by user

    zettel_info = []
    for ztl in zettels:
        zettel_info.append(f"<strong>[[{ztl.title}]]</strong><br>uuid: {ztl.uuid}, updated_at: {ztl.updated_at}<br>{ztl.content}")
    top_nav = "<h1>Zettel</h1><div><a href=\"/zettel/semantic_search/\">Semantic Search</a></div><br><hr>"
    return top_nav + "<div>" + "</div><hr><div>".join(zettel_info) + "</div>"

@zettel_bp.route('/semantic_search/')
def semantic_search():
    query = request.args.get('search_query')
    if query:
        # Perform semantic search using the query
        results = [] #perform_semantic_search(query)
        # TODO: Process the search results
        
        # Return the search results
        return "Search results: " + str(results)
    else:
        # Display the input field
        return """
        <form action="{url}" method="GET">
            <input type="text" name="search_query" placeholder="Enter your search query">
            <input type="submit" value="Search">
        </form>
        """.format(url=request.full_path)
