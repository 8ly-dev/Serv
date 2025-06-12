"""Pipeline system for audit event validation."""

from typing import Union


class AuditEventGroup:
    """Represents OR relationship - one of these events must occur."""

    def __init__(self, *events):
        from .events import AuditEventType
        # Validate all events are AuditEventType
        for event in events:
            if not isinstance(event, AuditEventType):
                raise ValueError(f"All events must be AuditEventType, got {type(event)}")
        self.events = tuple(events)

    def __or__(self, other):
        """OR this group with another event or group."""
        from .events import AuditEventType

        if isinstance(other, AuditEventGroup):
            return AuditEventGroup(*self.events, *other.events)
        elif isinstance(other, AuditEventType):
            return AuditEventGroup(*self.events, other)
        else:
            raise ValueError(f"Cannot OR {type(other)} with AuditEventGroup")

    def __ror__(self, other):
        """Reverse OR operation."""
        from .events import AuditEventType

        if isinstance(other, AuditEventGroup):
            return AuditEventGroup(*other.events, *self.events)
        elif isinstance(other, AuditEventType):
            return AuditEventGroup(other, *self.events)
        else:
            raise ValueError(f"Cannot OR {type(other)} with AuditEventGroup")

    def __rshift__(self, other):
        """Create pipeline starting with this group."""
        from .events import AuditEventType

        if isinstance(other, AuditEventType | AuditEventGroup):
            return AuditPipeline([self, other])
        elif isinstance(other, AuditPipeline):
            return AuditPipeline([self] + other.steps)
        else:
            raise ValueError(f"Cannot create pipeline with {type(other)}")

    def matches(self, events: list) -> bool:
        """Check if any of the events in this group occurred."""
        return any(event in events for event in self.events)

    def __repr__(self):
        return f"({' | '.join(e.value for e in self.events)})"

    def __eq__(self, other):
        if not isinstance(other, AuditEventGroup):
            return False
        return set(self.events) == set(other.events)

    def __hash__(self):
        return hash(self.events)


class AuditPipeline:
    """Represents a sequence of events that must occur in order."""

    def __init__(self, steps: list[Union['AuditEventType', 'AuditEventGroup']]):
        from .events import AuditEventType
        # Validate all steps
        for step in steps:
            if not isinstance(step, AuditEventType | AuditEventGroup):
                raise ValueError(f"Pipeline steps must be AuditEventType or AuditEventGroup, got {type(step)}")
        self.steps = list(steps)

    def __rshift__(self, other):
        """Extend pipeline with another step."""
        from .events import AuditEventType

        if isinstance(other, AuditEventType | AuditEventGroup):
            return AuditPipeline(self.steps + [other])
        elif isinstance(other, AuditPipeline):
            return AuditPipeline(self.steps + other.steps)
        else:
            raise ValueError(f"Cannot extend pipeline with {type(other)}")

    def __or__(self, other):
        """Create alternative pipeline - this pipeline OR that pipeline."""
        if isinstance(other, AuditPipeline):
            return AuditPipelineSet([self, other])
        elif isinstance(other, AuditPipelineSet):
            return AuditPipelineSet([self] + other.pipelines)
        else:
            raise ValueError(f"Cannot OR pipeline with {type(other)}")

    def __ror__(self, other):
        """Reverse OR operation."""
        if isinstance(other, AuditPipeline):
            return AuditPipelineSet([other, self])
        elif isinstance(other, AuditPipelineSet):
            return AuditPipelineSet(other.pipelines + [self])
        else:
            raise ValueError(f"Cannot OR {type(other)} with pipeline")

    def validates(self, events: list) -> bool:
        """Check if the events match this pipeline sequence."""
        from .events import AuditEventType

        event_index = 0

        for step in self.steps:
            if isinstance(step, AuditEventType):
                # Must find this exact event
                while event_index < len(events):
                    if events[event_index] == step:
                        event_index += 1
                        break
                    event_index += 1
                else:
                    return False  # Event not found

            elif isinstance(step, AuditEventGroup):
                # Must find one of the events in the group
                step_found = False
                while event_index < len(events):
                    if events[event_index] in step.events:
                        event_index += 1
                        step_found = True
                        break
                    event_index += 1

                if not step_found:
                    return False

        return True

    def __repr__(self):
        return ' >> '.join(str(step) for step in self.steps)

    def __eq__(self, other):
        if not isinstance(other, AuditPipeline):
            return False
        return self.steps == other.steps

    def __hash__(self):
        return hash(tuple(self.steps))


class AuditPipelineSet:
    """Represents multiple valid pipelines - any one of them can satisfy the requirement."""

    def __init__(self, pipelines: list[AuditPipeline]):
        for pipeline in pipelines:
            if not isinstance(pipeline, AuditPipeline):
                raise ValueError(f"All pipelines must be AuditPipeline, got {type(pipeline)}")
        self.pipelines = list(pipelines)

    def __or__(self, other):
        """Add another pipeline to this set."""
        if isinstance(other, AuditPipeline):
            return AuditPipelineSet(self.pipelines + [other])
        elif isinstance(other, AuditPipelineSet):
            return AuditPipelineSet(self.pipelines + other.pipelines)
        else:
            raise ValueError(f"Cannot OR pipeline set with {type(other)}")

    def validates(self, events: list) -> bool:
        """Check if events satisfy any of the pipelines."""
        return any(pipeline.validates(events) for pipeline in self.pipelines)

    def __repr__(self):
        return f"({' | '.join(str(p) for p in self.pipelines)})"

    def __eq__(self, other):
        if not isinstance(other, AuditPipelineSet):
            return False
        return set(self.pipelines) == set(other.pipelines)

    def __hash__(self):
        return hash(tuple(self.pipelines))
