# Loaded before any Python code on the public runners (the workflows set PYTHONPATH to this folder).
# Their logs are public, so tracebacks and warnings show file and line number only, never the source line.
import linecache

linecache.getline = lambda *args, **kwargs: ''
