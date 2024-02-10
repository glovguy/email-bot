# email-bot

This repository contains the code for an email bot. The bot utilizes event-driven LLMs (Language Models) and vector storage to maintain state and functionality.

## Skills

Skills are analogous to objects in Object-Oriented Programming (OOP). They listen to incoming events and store free text in vector storage. This approach allows for intuitive state management and easy implementation.

## BotBrain

BotBrain is the document storage collection for documents managed by the AI. It enables the creation, editing, and deletion of documents without human intervention. The vector storage collection is namespaced for each skill, allowing all data to be stored in one document store.

## Zettelkasten

The Zettelkasten is the document storage maintained by the users. Users can create, edit, and delete their own documents in this storage.
