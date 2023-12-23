class EventBus:
    listeners = {}
    command_listeners = {}

    # Events can have many listeners
    @classmethod
    def add_listener(cls, event_name, listener):
        if event_name not in cls.listeners:
            cls.listeners[event_name] = []
        cls.listeners[event_name].append(listener)

    @classmethod
    def dispatch_event(cls, event_name, *args, **kwargs):
        if event_name not in cls.listeners:
            return
        for listener in cls.listeners[event_name]:
            listener(*args, **kwargs)

    # Commands are messages with one listener
    @classmethod
    def register_command_listener(self, command_name, listener):
        self.command_listeners[command_name] = listener

    @classmethod
    def handle_command(self, command_name, *args, **kwargs):
        if command_name in self.command_listeners:
            listener = self.command_listeners[command_name]
            listener(*args, **kwargs)

def register_event_listener(event_name):
    def register_event(func):
        EventBus.add_listener(event_name, func)
        return func
    return register_event
