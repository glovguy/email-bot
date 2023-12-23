# email-bot

## skills

Often a first step for maintaining state with bots is to use a combination of prompts and the chat thread history. This has the upside of keeping track of state in an intuitive and easy to implement way. The downside is that it can be difficult to maintain very long threads, as well as it can be difficult to share state between threads.

Instead, I focus on pairing event-driven LLMs with vector storage. I don't like the term "agent", so I call these "skills". These are analogous to objects in OOP, since they maintain state as well as functionality.

Skills listen to incoming events and maintain free text in vector storage.

### BotBrain

BotBrain is the document storage collection for documents managed by the AI. These should be expected to be created, edited, and deleted without needing any human intervention.

The vector storage collection is namespaced for each skill so that all data can go in one document store without necessarily coming out of any arbitrary query.

### Zettelkasten

The Zettelkasten is the document storage maintained by the users. These are meant to be created, edited, and deleted by the users who own them.
