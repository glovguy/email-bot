from src.skills.bot_brain import BotBrain, botbrain_collection
from src.skills.get_to_know_you_skill import GET_TO_KNOW_DOC_NAMESPACE


def index():
    # docs = BotBrain.get_document(GET_TO_KNOW_DOC_NAMESPACE)
    docs = botbrain_collection.get(
            where={},
            ids=[]
        )
    render_note = render_notes(docs)
    return "<h1>Skills</h1><h2>BotBrain</h2><ol><li><pre>" + \
        "</pre></li><li><pre>".join(map(render_note, range(0,len(docs['documents'])))) + \
        "</pre></li></ol>"

def render_notes(docs):
    def render_note(i):
        return str(docs['documents'][i]) + \
            "\n\n{\n    " + \
            ",\n    ".join([str(k)+": "+str(v) for (k,v) in docs['metadatas'][i].items()]) + \
            "\n}"

    return render_note
