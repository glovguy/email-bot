class EventBus:
    listeners = {}

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
