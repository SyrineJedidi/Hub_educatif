from django.dispatch import Signal

# Sent after commit with course_id, resource_id (or None) and reason; ids are strings.
course_content_changed = Signal()
